"""Linux local cache ownership, reservations, leases and conservative explicit GC.

The evidence registry is separate. Nothing here adopts arbitrary external files.
All cooperating writers serialize metadata decisions with a per-store flock.
"""
from contextlib import contextmanager
try:
    import fcntl
except ImportError:  # Contracts/read-only --no-cache remain usable without Linux lifecycle.
    fcntl = None
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import time
import uuid

from .core import atomic_json, canonical, file_hash, object_hash, read_json


def process_identity(pid=None):
    pid = pid or os.getpid()
    try:
        p = Path('/proc') / str(pid)
        fields = (p / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'start_ticks': fields[19],
                'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'uid': p.stat().st_uid, 'state': fields[0]}
    except (OSError, IndexError):
        return None


def process_alive(identity):
    if not identity:
        return False
    actual = process_identity(identity['pid'])
    return bool(actual and actual['state'] != 'Z' and all(actual[k] == identity[k] for k in ('pid', 'start_ticks', 'boot_id', 'uid')))


def object_relative(item_id):
    if not isinstance(item_id, str) or not re.fullmatch(r'(query|namespace|job):[0-9a-f]{64}', item_id):
        raise ValueError('Invalid managed object ID')
    kind, key = item_id.split(':')
    return {'query': 'queries/' + key + '.json', 'namespace': 'namespaces/' + key, 'job': 'jobs/' + key}[kind]


def snapshot(path, digest=False):
    """Never traverse symlinks; refuse foreign ownership and shared hardlinks."""
    path = Path(path)
    root = path.lstat()
    entries, inodes = [], set()
    logical = physical = 0
    paths = [path]
    while paths:
        p = paths.pop()
        s = p.lstat()
        if stat.S_ISLNK(s.st_mode):
            raise ValueError('Managed path must not be a symlink: ' + str(p))
        if s.st_uid != os.getuid():
            raise ValueError('Managed path has a foreign owner')
        if stat.S_ISDIR(s.st_mode):
            with os.scandir(p) as children:
                paths.extend(Path(e.path) for e in children)
        elif stat.S_ISREG(s.st_mode):
            if s.st_nlink != 1:
                raise ValueError('Shared hardlinks are protected')
            logical += s.st_size
            if (s.st_dev, s.st_ino) not in inodes:
                physical += s.st_blocks * 512
                inodes.add((s.st_dev, s.st_ino))
            if digest:
                entries.append([str(p.relative_to(path)) if p != path else '.', s.st_size, file_hash(p)])
        else:
            raise ValueError('Special filesystem objects are protected')
        if len(paths) + len(inodes) > 100000:
            raise ValueError('Cache scan exceeded file-count budget')
    return {'bytes': logical, 'physical_bytes': physical, 'device': root.st_dev, 'inode': root.st_ino,
            'sha256': (object_hash(sorted(entries)) if path.is_dir() else file_hash(path)) if digest else None}


class CacheStore:
    def __init__(self, settings):
        self.settings = settings
        self.root = settings.cache_dir
        self.meta = self.root / '.rdnascope'

    def path(self, item_id):
        path = self.root / object_relative(item_id)
        for p in [self.root, *reversed(path.relative_to(self.root).parents), path.relative_to(self.root)]:
            candidate = p if p == self.root else self.root / p
            if candidate.is_symlink():
                raise ValueError('Managed cache path must not be a symlink')
        return path

    @contextmanager
    def locked(self):
        if fcntl is None or not Path('/proc/sys/kernel/random/boot_id').exists():
            raise ValueError('Managed lifecycle requires Linux /proc and flock; offline query --no-cache is available')
        if self.root.is_symlink() or self.meta.is_symlink():
            raise ValueError('Managed cache directory must not be a symlink')
        self.meta.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.meta / 'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            if os.fstat(fd).st_uid != os.getuid() or os.fstat(fd).st_nlink != 1:
                raise ValueError('Foreign/shared store lock is protected')
            fcntl.flock(fd, fcntl.LOCK_EX)
            marker = self.meta / 'owner.json'
            if marker.is_symlink():
                raise ValueError('Store owner marker must not be a symlink')
            if not marker.exists():
                atomic_json(marker, {'schema_version': 1, 'uid': os.getuid(), 'root': str(self.root), 'store_id': uuid.uuid4().hex})
            owner = read_json(marker)
            if owner.get('schema_version') != 1 or owner.get('uid') != os.getuid() or owner.get('root') != str(self.root):
                raise ValueError('Cache ownership/root mismatch; no adoption or deletion performed')
            db = self.meta / 'index.sqlite3'
            if db.exists() and (db.is_symlink() or db.stat().st_uid != os.getuid() or db.stat().st_nlink != 1):
                raise ValueError('Foreign/shared lifecycle index is protected')
            c = sqlite3.connect(db)
            c.row_factory = sqlite3.Row
            try:
                version = c.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0, 1):
                    raise ValueError('Unsupported lifecycle index version')
                if version == 0:
                    if c.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]:
                        raise ValueError('Unversioned lifecycle index is protected')
                    c.executescript('''
                        CREATE TABLE items(id TEXT PRIMARY KEY, kind TEXT NOT NULL, bytes INTEGER NOT NULL,
                            sha TEXT NOT NULL, accessed_ns INTEGER NOT NULL, created_ns INTEGER NOT NULL,
                            status TEXT NOT NULL, metadata TEXT NOT NULL);
                        CREATE TABLE refs(item TEXT NOT NULL, reference TEXT NOT NULL, PRIMARY KEY(item,reference));
                        CREATE TABLE leases(id TEXT PRIMARY KEY, item TEXT NOT NULL, identity TEXT NOT NULL,
                            purpose TEXT NOT NULL, reserved INTEGER NOT NULL, base_bytes INTEGER NOT NULL,
                            writer INTEGER NOT NULL);
                        CREATE TABLE plans(id TEXT PRIMARY KEY, body TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0);
                        CREATE TABLE audit(id INTEGER PRIMARY KEY, at_ns INTEGER NOT NULL, action TEXT NOT NULL, body TEXT NOT NULL);
                        CREATE TABLE jobs(id TEXT PRIMARY KEY, spec TEXT NOT NULL, supervisor TEXT,
                            child TEXT, status TEXT NOT NULL, stop_requested INTEGER NOT NULL DEFAULT 0, result TEXT);
                        PRAGMA user_version=1;
                    ''')
                self.store_id = owner['store_id']
                with c:
                    yield c
            finally:
                c.close()
        finally:
            os.close(fd)

    @staticmethod
    def audit(c, action, body):
        c.execute('INSERT INTO audit(at_ns,action,body) VALUES(?,?,?)', (time.time_ns(), action, canonical(body)))

    def _leases(self, c):
        return [dict(r, active=process_alive(json.loads(r['identity']))) for r in c.execute('SELECT * FROM leases')]

    def _usage(self):
        return snapshot(self.root) if self.root.exists() else {'bytes': 0, 'physical_bytes': 0}

    def _budget(self, c, requested=0, excluding=None):
        if type(requested) is not int or requested < 0:
            raise ValueError('Reservation bytes must be nonnegative')
        reasons = []
        errors = []
        try:
            usage = self._usage()
        except (ValueError, OSError) as exc:
            usage = {'bytes': None, 'physical_bytes': None}
            reasons.append('unsafe_cache_tree');errors.append(str(exc))
        reservations = 0
        for lease in self._leases(c):
            if not lease['active'] or lease['id'] == excluding:
                continue
            try:
                path = self.path(lease['item'])
                current = snapshot(path)['bytes'] if path.exists() else 0
            except (ValueError,OSError) as exc:
                reasons.append('unsafe_leased_object');errors.append(str(exc));current = lease['base_bytes']
            reservations += max(0, lease['reserved'] - max(0, current - lease['base_bytes']))
        anchor = self.root
        while not anchor.exists():
            anchor = anchor.parent
        free = shutil.disk_usage(anchor).free
        policy = self.settings.storage_policy
        if policy['max_bytes'] is not None and usage['bytes'] is not None and usage['bytes'] + reservations + requested > policy['max_bytes']:
            reasons.append('cache_quota_exceeded')
        if policy['min_free_bytes'] is not None and free - reservations - requested < policy['min_free_bytes']:
            reasons.append('disk_reserve_would_be_violated')
        return {'status': 'blocked' if reasons else 'pass', 'reasons': reasons, 'policy': policy,
                'cache_bytes': usage['bytes'], 'cache_physical_bytes': usage['physical_bytes'],
                'active_reserved_bytes': reservations, 'requested_bytes': requested, 'filesystem_free_bytes': free,
                'safety_errors': errors,
                'policy_configured': any(v is not None for v in policy.values()), 'automatic_gc': False}

    def preflight(self, requested=0):
        with self.locked() as c:
            return self._budget(c, requested)

    @contextmanager
    def lease(self, item_id, purpose, reserve=0, writer=False):
        path = self.path(item_id)
        token = uuid.uuid4().hex
        with self.locked() as c:
            active = [l for l in self._leases(c) if l['active'] and l['item'] == item_id]
            if active and (writer or any(l['writer'] for l in active)):
                raise ValueError('Managed object is busy; active lease protects it')
            budget = self._budget(c, reserve)
            if reserve and budget['status'] != 'pass':
                raise ValueError('Storage budget blocked: ' + ', '.join(budget['reasons']))
            base = snapshot(path)['bytes'] if path.exists() else 0
            c.execute('INSERT INTO leases VALUES(?,?,?,?,?,?,?)',
                      (token, item_id, canonical(process_identity()), purpose, reserve, base, int(writer)))
        try:
            yield token
        finally:
            with self.locked() as c:
                c.execute('DELETE FROM leases WHERE id=?', (token,))

    def _record(self, c, item_id, metadata, status='ready'):
        current = snapshot(self.path(item_id), digest=True)
        now = time.time_ns()
        old = c.execute('SELECT created_ns FROM items WHERE id=?', (item_id,)).fetchone()
        c.execute('INSERT OR REPLACE INTO items VALUES(?,?,?,?,?,?,?,?)',
                  (item_id, item_id.split(':')[0], current['bytes'], current['sha256'], now,
                   old[0] if old else now, status, canonical(metadata)))
        return current

    def verify(self, item_id):
        with self.locked() as c:
            item = c.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
            if not item:
                return False  # R1/unmanaged files are never silently adopted for GC.
            if item['status'] != 'ready' or snapshot(self.path(item_id), True)['sha256'] != item['sha']:
                raise ValueError('Derived cache object failed integrity check; original evidence was not modified')
            c.execute('UPDATE items SET accessed_ns=? WHERE id=?', (time.time_ns(), item_id))
            return True

    def publish_query(self, key, value, lease):
        item_id = 'query:' + key
        data = (canonical(value) + '\n').encode()
        with self.locked() as c:
            live = c.execute('SELECT * FROM leases WHERE id=? AND item=?', (lease, item_id)).fetchone()
            if not live or not process_alive(json.loads(live['identity'])):
                raise ValueError('Active publication lease required')
            path = self.path(item_id)
            if path.exists():
                raise ValueError('Refusing to overwrite an existing query cache object')
            budget = self._budget(c, len(data), excluding=lease)
            if budget['status'] != 'pass':
                raise ValueError('Storage budget blocked at publication: ' + ', '.join(budget['reasons']))
            atomic_json(path, value)
            self._record(c, item_id, {'query_id': key, 'regenerable': True})

    def create_directory(self, item_id, metadata):
        if item_id.startswith('query:'):
            raise ValueError('Directory objects must be namespaces or jobs')
        with self.locked() as c:
            path = self.path(item_id)
            existing = c.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
            if existing and existing['status'] == 'ready':
                if json.loads(existing['metadata']) != metadata:
                    raise ValueError('Managed directory identity differs')
                if snapshot(path, True)['sha256'] != existing['sha']:
                    raise ValueError('Managed directory changed outside its writer lease')
                c.execute('UPDATE items SET accessed_ns=? WHERE id=?', (time.time_ns(), item_id))
                return path
            if path.exists():
                raise ValueError('Unmanaged existing directory is protected')
            if self._budget(c, 4096)['status'] != 'pass':
                raise ValueError('Storage budget blocked before directory creation')
            path.mkdir(parents=True)
            atomic_json(path / 'owner.json', {'store_id': self.store_id, 'item': item_id, 'uid': os.getuid()})
            self._record(c, item_id, metadata)
            return path

    def seal(self, item_id, token, status='ready'):
        with self.locked() as c:
            lease = c.execute('SELECT * FROM leases WHERE id=? AND item=? AND writer=1', (token, item_id)).fetchone()
            if not lease or not process_alive(json.loads(lease['identity'])):
                raise ValueError('Sealing requires this live writer lease')
            item = c.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
            self._record(c, item_id, json.loads(item['metadata']), status)

    def check_reservation(self, token):
        with self.locked() as c:
            lease = c.execute('SELECT * FROM leases WHERE id=?', (token,)).fetchone()
            if not lease:
                raise ValueError('Unknown worker lease')
            path = self.path(lease['item'])
            growth = max(0, snapshot(path)['bytes'] - lease['base_bytes']) if path.exists() else 0
            result = self._budget(c, max(0, lease['reserved'] - growth), excluding=token)
            if growth > lease['reserved']:
                result['status'] = 'blocked'
                result['reasons'].append('worker_reservation_exceeded')
            return result

    def reference(self, item_id, reference, remove=False):
        object_relative(item_id)
        if not isinstance(reference, str) or not reference.strip() or len(reference) > 256:
            raise ValueError('A nonempty reference of at most 256 characters is required')
        with self.locked() as c:
            item = c.execute('SELECT status FROM items WHERE id=?', (item_id,)).fetchone()
            if not item or item['status'] not in ('ready', 'quarantined'):
                raise ValueError('Only a ready managed object can be pinned/referenced')
            if remove:
                c.execute('DELETE FROM refs WHERE item=? AND reference=?', (item_id, reference))
            else:
                c.execute('INSERT OR IGNORE INTO refs VALUES(?,?)', (item_id, reference))
            self.audit(c, 'reference_removed' if remove else 'reference_added', {'item': item_id, 'reference': reference})
        return {'item': item_id, 'reference': reference, 'protected': not remove}

    def inventory(self):
        with self.locked() as c:
            leases = self._leases(c)
            items = []
            for row in c.execute('SELECT * FROM items ORDER BY accessed_ns,id'):
                item = dict(row)
                item['metadata'] = json.loads(item['metadata'])
                item['references'] = [r[0] for r in c.execute('SELECT reference FROM refs WHERE item=? ORDER BY reference', (item['id'],))]
                item['leases'] = [l for l in leases if l['item'] == item['id']]
                item['path'] = str(self.root / object_relative(item['id']))
                try:
                    path=self.path(item['id'])
                    current=snapshot(path) if path.exists() else None
                    item['bytes_available']=current is not None
                    item['actual_bytes']=current['bytes'] if current else 0
                except (ValueError,OSError) as exc:
                    item['safety_error']=str(exc);item['bytes_available']=False;item['actual_bytes']=None
                item['reusable'] = item['status'] == 'ready' and item['bytes_available']
                items.append(item)
            return {'store_id': self.store_id, 'items': items, 'budget': self._budget(c),
                    'unmanaged_policy': 'protected; no automatic adoption', 'external_policy': 'never_deleted'}

    def summary(self):
        if not (self.meta / 'owner.json').exists():
            return {'initialized': False, 'policy': self.settings.storage_policy,
                    'unmanaged_cache_bytes': self._usage()['bytes'], 'automatic_gc': False}
        inventory = self.inventory()
        by_kind = {}
        actual_by_kind = {}
        for item in inventory['items']:
            if item['bytes_available']:
                by_kind[item['kind']] = by_kind.get(item['kind'], 0) + item['bytes']
                actual_by_kind[item['kind']] = actual_by_kind.get(item['kind'], 0) + item['actual_bytes']
        control=snapshot(self.meta)['bytes']
        total=inventory['budget']['cache_bytes']
        return {'initialized': True, 'store_id': inventory['store_id'], 'budget': inventory['budget'],
                'catalogued_bytes_by_kind': by_kind,
                'managed_current_bytes_by_kind': actual_by_kind, 'control_metadata_bytes': control,
                'unmanaged_cache_bytes': max(0,total-control-sum(actual_by_kind.values())) if total is not None else None,
                'protected_by_reference': sum(bool(item['references']) for item in inventory['items']),
                'active_leases': sum(l['active'] for item in inventory['items'] for l in item['leases']),
                'tombstones': sum(item['status'] == 'deleted' for item in inventory['items']),
                'limits': ['Catalogue bytes are last sealed sizes; budget scans current files',
                           'Control metadata and unmanaged files count toward cache quota but are never GC candidates',
                           'Process RSS/PSS and external evidence are separate from cache disk bytes']}

    @staticmethod
    def _job_references(c):
        protected=set()
        for job in c.execute("SELECT id,spec FROM jobs WHERE status IN ('queued','running')"):
            protected.add(job['id'])
            namespace=json.loads(job['spec']).get('namespace')
            if namespace:protected.add(namespace)
        return protected

    def gc_preview(self, older_than=None, reclaim_bytes=None):
        ttl = self.settings.storage_policy['ttl_seconds'] if older_than is None else older_than
        if ttl is not None and (type(ttl) is not int or ttl < 0):
            raise ValueError('GC age must be nonnegative integer seconds')
        if reclaim_bytes is not None and (type(reclaim_bytes) is not int or reclaim_bytes <= 0):
            raise ValueError('GC target bytes must be positive')
        with self.locked() as c:
            now = time.time_ns()
            leases = self._leases(c)
            jobs = self._job_references(c)
            candidates, protected, selected_bytes = [], [], 0
            for r in c.execute('SELECT * FROM items ORDER BY accessed_ns,id').fetchall():
                item = dict(r); reasons = []
                if item['status'] not in ('ready', 'quarantined'): reasons.append('not_ready_or_tombstoned')
                if c.execute('SELECT 1 FROM refs WHERE item=?', (item['id'],)).fetchone(): reasons.append('pinned_or_referenced')
                if any(l['active'] and l['item'] == item['id'] for l in leases): reasons.append('active_lease')
                if item['id'] in jobs:reasons.append('active_or_unreconciled_job')
                if ttl is None: reasons.append('ttl_not_configured')
                elif now - item['accessed_ns'] < ttl * 1000000000: reasons.append('recently_used')
                current = None
                if not reasons:
                    try:
                        current = snapshot(self.path(item['id']), True)
                        if current['sha256'] != item['sha']: reasons.append('content_changed')
                    except (ValueError, OSError) as exc:
                        reasons.append('unsafe_or_missing: ' + str(exc))
                if reclaim_bytes and selected_bytes >= reclaim_bytes: reasons.append('reclaim_target_met')
                if reasons:
                    protected.append({'id': item['id'], 'reasons': reasons})
                else:
                    candidates.append({'id': item['id'], 'bytes': current['bytes'], 'sha256': current['sha256'],
                                       'accessed_ns': item['accessed_ns'], 'device': current['device'], 'inode': current['inode']})
                    selected_bytes += current['bytes']
            body = {'schema_version': 1, 'store_id': self.store_id, 'created_ns': now,
                    'policy': {'older_than_seconds': ttl, 'reclaim_bytes': reclaim_bytes, 'order': 'least_recently_used'},
                    'candidates': candidates, 'protected': protected, 'expected_reclaimed_bytes': selected_bytes,
                    'unmanaged_and_external': 'excluded', 'execution': 'explicit_plan_required'}
            plan = dict(body, plan_id=object_hash(body))
            c.execute('INSERT INTO plans(id,body) VALUES(?,?)', (plan['plan_id'], canonical(plan)))
            return plan

    def gc_apply(self, plan):
        deleted, skipped = [], []
        with self.locked() as c:
            original = c.execute('SELECT * FROM plans WHERE id=?', (plan.get('plan_id'),)).fetchone()
            if not original or original['body'] != canonical(plan) or plan.get('store_id') != self.store_id or original['consumed']:
                raise ValueError('GC plan is unknown, changed, from another store or already consumed')
            for target in plan['candidates']:
                item_id = target['id']
                r = c.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
                reasons = []
                if not r or r['status'] not in ('ready', 'quarantined'): reasons.append('not_ready')
                elif r['accessed_ns'] != target['accessed_ns'] or r['sha'] != target['sha256']: reasons.append('changed_since_preview')
                if c.execute('SELECT 1 FROM refs WHERE item=?', (item_id,)).fetchone(): reasons.append('pinned_or_referenced')
                if any(l['active'] and l['item'] == item_id for l in self._leases(c)): reasons.append('active_lease')
                if item_id in self._job_references(c):reasons.append('active_or_unreconciled_job')
                path = self.path(item_id)
                if not reasons:
                    try:
                        current = snapshot(path, True)
                        if any(current[k] != target[k] for k in ('bytes', 'sha256', 'device', 'inode')): reasons.append('filesystem_changed_since_preview')
                    except (ValueError, OSError) as exc:
                        reasons.append('unsafe_or_missing: ' + str(exc))
                if reasons:
                    skipped.append({'id': item_id, 'reasons': reasons})
                    continue
                # Persist intent first. Interrupted deletion remains protected until reconcile.
                c.execute("UPDATE items SET status='deleting' WHERE id=?", (item_id,))
                self.audit(c, 'delete_intent', target)
                c.commit()
                if path.is_dir():
                    if not shutil.rmtree.avoids_symlink_attacks:
                        raise ValueError('This platform lacks safe directory removal')
                    shutil.rmtree(path)
                else:
                    path.unlink()
                c.execute("UPDATE items SET status='deleted' WHERE id=?", (item_id,))
                self.audit(c, 'deleted', target)
                deleted.append(target)
            c.execute('UPDATE plans SET consumed=1 WHERE id=?', (plan['plan_id'],))
            result = {'plan_id': plan['plan_id'], 'deleted': deleted, 'skipped': skipped,
                      'reclaimed_bytes': sum(t['bytes'] for t in deleted), 'external_deleted': False}
            self.audit(c, 'gc_complete', result)
            return result

    def reconcile(self):
        with self.locked() as c:
            recovered = []
            for r in c.execute("SELECT id FROM items WHERE status='deleting'").fetchall():
                if not self.path(r['id']).exists():
                    c.execute("UPDATE items SET status='deleted' WHERE id=?", (r['id'],))
                    recovered.append(r['id'])
            dead = [l['id'] for l in self._leases(c) if not l['active']]
            if dead:
                c.executemany('DELETE FROM leases WHERE id=?', [(value,) for value in dead])
            abandoned=[]
            for job in c.execute("SELECT * FROM jobs WHERE status IN ('queued','running')").fetchall():
                if not process_alive(json.loads(job['supervisor']) if job['supervisor'] else None):
                    result={'reason':'supervisor_missing','child_alive':process_alive(json.loads(job['child']) if job['child'] else None),'cleanup':'not_assumed'}
                    c.execute("UPDATE jobs SET status='abandoned',result=? WHERE id=?",(canonical(result),job['id']))
                    c.execute('INSERT OR IGNORE INTO refs VALUES(?,?)',(job['id'],'abandoned-job-evidence'))
                    namespace=json.loads(job['spec']).get('namespace')
                    if namespace:c.execute('INSERT OR IGNORE INTO refs VALUES(?,?)',(namespace,'abandoned-job:'+job['id']))
                    abandoned.append(job['id'])
            self.audit(c, 'reconcile', {'completed_tombstones': recovered, 'dead_leases_removed': len(dead),'abandoned_jobs':abandoned})
            return {'completed_tombstones': recovered, 'dead_leases_removed': len(dead), 'abandoned_jobs':abandoned,'files_deleted': False}

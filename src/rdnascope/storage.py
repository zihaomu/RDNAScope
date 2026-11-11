"""Small transactional registry. Original evidence is referenced, never copied."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from urllib.parse import unquote, urlparse

from .core import canonical, file_hash, identifier, object_hash, validate


def local_path(uri):
    parsed = urlparse(uri)
    if parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost'):
        raise ValueError('Only local read-only file evidence is supported')
    return Path(unquote(parsed.path))


def sealed(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('Evidence must be a regular file')
    for suffix in ('-wal', '-journal'):
        p = Path(str(path) + suffix)
        if p.exists() and p.stat().st_size:
            raise ValueError('Unsealed SQLite evidence has a WAL/journal; finish/checkpoint its writer before registration')
    return path


def sqlite_readonly(path):
    path = sealed(path)
    connection = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    return connection


class Registry:
    def __init__(self, settings):
        self.settings = settings
        self.path = settings.data_dir / 'registry.sqlite3'

    @contextmanager
    def connection(self, write=False):
        if self.path.is_symlink():
            raise ValueError('Registry must not be a symlink')
        existed = self.path.exists()
        if not existed and not write:
            raise FileNotFoundError('No registry; register an explicit input first')
        if write:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(self.path, timeout=10)
        else:
            c = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
        c.row_factory = sqlite3.Row
        try:
            if write:
                c.execute('BEGIN IMMEDIATE')
            version = c.execute('PRAGMA user_version').fetchone()[0]
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if version not in (0, 1) or version == 0 and (tables or not write):
                raise ValueError('Unsupported registry schema; preserve the file and use a compatible reader')
            if version == 0:
                statements = '''
                    CREATE TABLE runs(run_id TEXT PRIMARY KEY, identity_json TEXT NOT NULL, identity_sha TEXT NOT NULL);
                    CREATE TABLE objects(artifact_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL, format TEXT NOT NULL);
                    CREATE TABLE inputs(run_id TEXT NOT NULL, artifact_id TEXT NOT NULL, uri TEXT NOT NULL, role TEXT NOT NULL,
                                        PRIMARY KEY(run_id,artifact_id,uri));
                    CREATE TABLE derivations(run_id TEXT NOT NULL, child TEXT NOT NULL, parent TEXT NOT NULL,
                                             PRIMARY KEY(run_id,child,parent));
                    PRAGMA user_version=1;
                '''
                for statement in statements.split(';'):
                    if statement.strip():
                        c.execute(statement)
            with c:
                yield c
        finally:
            if c.in_transaction:
                c.rollback()
            c.close()

    def register(self, identity, entries):
        from .providers import detect_format
        identity = validate('identity', identity)
        run = identifier(identity['run_id'])
        if self.path.exists():
            with self.connection() as c:
                if c.execute('SELECT 1 FROM runs WHERE run_id=?', (run,)).fetchone():
                    raise FileExistsError('Run is immutable and already registered; use a new run ID')
        artifacts, labels = [], {}
        for i, entry in enumerate(entries):
            if set(entry) - {'path', 'format', 'label', 'derived_from'}:
                raise ValueError('Unknown registration entry field')
            path = Path(entry['path']).expanduser().resolve(strict=True)
            label = identifier(entry.get('label', 'input-' + str(i)))
            if label in labels:
                raise ValueError('Duplicate input label')
            if path.is_dir():
                if entry.get('format', 'auto') not in ('auto', 'tlp-legacy'):
                    raise ValueError('Directories are supported only for normalized legacy datasets')
                paths = [(path / 'manifest.json', 'legacy_manifest'),
                         (path / 'normalized/events.jsonl', 'legacy_events')]
            else:
                paths = [(path, entry.get('format', 'auto'))]
            ids = []
            for source, fmt in paths:
                source = sealed(source)
                if source == self.path.resolve() or source.is_relative_to(self.settings.cache_dir.resolve()):
                    raise ValueError('Registry/cache files cannot be source evidence')
                fmt = detect_format(source, fmt, self.settings)
                sha = file_hash(source)
                artifact = validate('artifact', {'schema_version': 1, 'artifact_id': 'sha256:' + sha,
                    'sha256': sha, 'bytes': source.stat().st_size, 'format': fmt, 'uri': source.as_uri(),
                    'storage': 'external_read_only',
                    'role': fmt if fmt.startswith('legacy_') else 'input'})
                artifacts.append(artifact); ids.append(artifact['artifact_id'])
            if len(ids) != 1 and entry.get('derived_from'):
                raise ValueError('Declare derivations on individual files, not legacy directories')
            labels[label] = ids
        if not artifacts:
            raise ValueError('At least one explicit input is required')
        formats = {a['format'] for a in artifacts}
        if ('legacy_manifest' in formats) != ('legacy_events' in formats):
            raise ValueError('Legacy manifest and normalized events must be registered together')
        if 'legacy_manifest' in formats and (formats != {'legacy_manifest', 'legacy_events'} or len(artifacts) != 2):
            raise ValueError('Register one complete legacy dataset per run')
        edges = []
        for i, entry in enumerate(entries):
            child = labels[entry.get('label', 'input-' + str(i))][0]
            for parent_label in entry.get('derived_from', []):
                if parent_label not in labels or len(labels[parent_label]) != 1:
                    raise ValueError('Derivation parent must name one registered file')
                parent = labels[parent_label][0]
                if child == parent:
                    raise ValueError('Self/cyclic derivation')
                edges.append((child, parent))
        graph = {}
        for child, parent in edges:
            graph.setdefault(child, []).append(parent)
        def visit(node, active):
            if node in active:
                raise ValueError('Cyclic derivation')
            for parent in graph.get(node, []):
                visit(parent, active | {node})
        for node in graph:
            visit(node, set())
        self.verify(artifacts)
        try:
            with self.connection(write=True) as c:
                c.execute('INSERT INTO runs VALUES(?,?,?)', (run, canonical(identity), object_hash(identity)))
                for a in artifacts:
                    old = c.execute('SELECT format FROM objects WHERE artifact_id=?', (a['artifact_id'],)).fetchone()
                    if old and old['format'] != a['format']:
                        raise ValueError('Same bytes registered with conflicting formats')
                    c.execute('INSERT OR IGNORE INTO objects VALUES(?,?,?,?)',
                              (a['artifact_id'], a['sha256'], a['bytes'], a['format']))
                    c.execute('INSERT INTO inputs VALUES(?,?,?,?)', (run, a['artifact_id'], a['uri'], a['role']))
                for child, parent in edges:
                    c.execute('INSERT INTO derivations VALUES(?,?,?)', (run, child, parent))
        except sqlite3.IntegrityError as exc:
            raise ValueError('Registration conflict; no partial run was committed') from exc
        return self.inspect(run)

    @staticmethod
    def verify(artifacts):
        for a in artifacts:
            path = sealed(local_path(a['uri']))
            if path.stat().st_size != a['bytes'] or file_hash(path) != a['sha256']:
                raise ValueError('Evidence changed; refusing query/cache reuse: ' + a['artifact_id'])

    def inspect(self, run):
        identifier(run)
        with self.connection() as c:
            r = c.execute('SELECT * FROM runs WHERE run_id=?', (run,)).fetchone()
            if not r:
                raise ValueError('Unknown run: ' + run)
            identity = validate('identity', json.loads(r['identity_json']))
            if object_hash(identity) != r['identity_sha']:
                raise ValueError('Registered identity hash mismatch')
            rows = c.execute('SELECT i.*,o.sha256,o.bytes,o.format FROM inputs i JOIN objects o USING(artifact_id) WHERE run_id=? ORDER BY artifact_id,uri', (run,)).fetchall()
            artifacts = [validate('artifact', {'schema_version': 1, 'artifact_id': a['artifact_id'],
                         'sha256': a['sha256'], 'bytes': a['bytes'], 'format': a['format'], 'uri': a['uri'],
                         'storage': 'external_read_only', 'role': a['role']}) for a in rows]
            edges = [dict(row) for row in c.execute('SELECT child,parent FROM derivations WHERE run_id=? ORDER BY child,parent', (run,))]
        self.verify(artifacts)
        return {'schema_version': 1, 'identity': identity, 'artifacts': artifacts,
                'derivations': [{'child': e['child'], 'parent': e['parent'], 'status': 'declared_not_semantically_audited'} for e in edges],
                'registered_bytes_verified': True,
                'limits': ['Registration verifies explicit bytes, not model correctness, clocks or collection completeness']}

    def stats(self):
        from .lifecycle import CacheStore
        runs, logical, rows = 0, 0, []
        if self.path.exists():
            with self.connection() as c:
                runs = c.execute('SELECT count(*) FROM runs').fetchone()[0]
                logical = c.execute('SELECT coalesce(sum(bytes),0) FROM objects').fetchone()[0]
                rows = c.execute('SELECT DISTINCT uri FROM inputs').fetchall()
        inodes, external_physical, missing = set(), 0, []
        for row in rows:
            path = local_path(row['uri'])
            try:
                s = path.stat()
                key = (s.st_dev, s.st_ino)
                if key not in inodes:
                    inodes.add(key); external_physical += s.st_blocks * 512
            except FileNotFoundError:
                missing.append(row['uri'])
        cache_files = [p for p in (self.settings.cache_dir / 'queries').glob('*.json') if not p.is_symlink()]
        return {'runs': runs, 'external_unique_content_bytes': logical,
                'external_physical_bytes_for_registered_locations': external_physical,
                'external_missing_locations': missing, 'source_bytes_copied': 0,
                'registry_bytes': self.path.stat().st_size if self.path.exists() else 0,
                'derived_query_cache_files': len(cache_files),
                'derived_query_cache_bytes': sum(p.stat().st_size for p in cache_files),
                'deletion_performed': False, 'retention_enforcement': 'explicit_managed_gc_only_no_automatic_gc',
                'lifecycle': CacheStore(self.settings).summary(),
                'limits': ['External locations remain user-owned; registry does not delete them',
                           'RSS/PSS, GPU memory and compiler caches are not included in these disk statistics']}

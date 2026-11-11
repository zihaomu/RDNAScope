"""Owned Linux process groups, bounded logs/scratch and upstream Perfetto services."""
from contextlib import ExitStack
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

from .core import Settings, atomic_json, file_hash, identifier, object_hash, read_json
from .lifecycle import CacheStore, process_alive, process_identity, snapshot
from . import namespaces


def memory(identity):
    if not process_alive(identity):
        return {'rss_bytes': None, 'pss_bytes': None, 'source': 'process_not_live'}
    result = {'rss_bytes': None, 'pss_bytes': None, 'source': 'linux_proc_smaps_rollup'}
    try:
        for line in (Path('/proc') / str(identity['pid']) / 'smaps_rollup').read_text().splitlines():
            if line.startswith('Rss:'): result['rss_bytes'] = int(line.split()[1]) * 1024
            if line.startswith('Pss:'): result['pss_bytes'] = int(line.split()[1]) * 1024
    except OSError:
        result['source'] = 'unavailable'
    return result


def _job_update(store, job_id, **fields):
    allowed = {'supervisor', 'child', 'status', 'stop_requested', 'result'}
    if set(fields) - allowed:
        raise ValueError('Unknown job update field')
    with store.locked() as c:
        values = [canonical_json(v) if isinstance(v, (dict, list)) else v for v in fields.values()]
        c.execute('UPDATE jobs SET ' + ','.join(k + '=?' for k in fields) + ' WHERE id=?', [*values, job_id])


def canonical_json(value):
    from .core import canonical
    return canonical(value)


def status(settings, job_id=None):
    store = CacheStore(settings)
    with store.locked() as c:
        rows = c.execute('SELECT * FROM jobs' + (' WHERE id=?' if job_id else '') + ' ORDER BY rowid DESC LIMIT 101', (job_id,) if job_id else ()).fetchall()
        if job_id and not rows:
            raise ValueError('Unknown managed job/service; external processes are not adopted')
        results = []
        for row in rows[:100]:
            job = dict(row)
            for key in ('spec', 'supervisor', 'child', 'result'):
                job[key] = json.loads(job[key]) if job[key] is not None else None
            job['supervisor_alive'] = process_alive(job['supervisor'])
            job['child_alive'] = process_alive(job['child'])
            job['memory'] = memory(job['child'])
            job['supervisor_memory'] = memory(job['supervisor'])
            job['logs'] = str(store.path(job['id']))
            job['logs_available'] = Path(job['logs']).is_dir()
            stored = c.execute('SELECT status FROM items WHERE id=?',(job['id'],)).fetchone()
            job['log_storage_status'] = stored[0] if stored else 'unknown'
            if job['status'] in ('queued', 'running') and not job['supervisor_alive']:
                job['observed_state'] = 'supervisor_missing; not safe to assume successful cleanup'
            results.append(job)
        return results[0] if job_id else {'jobs': results, 'has_more': len(rows)>100, 'external_services': 'not_adopted_or_signalled'}


def stop(settings, job_id):
    store = CacheStore(settings)
    with store.locked() as c:
        job = c.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise ValueError('Unknown managed job/service; no PID was signalled')
        if job['status'] not in ('queued', 'running'):
            return {'job': job_id, 'status': job['status'], 'stop_requested': False}
        if not process_alive(json.loads(job['supervisor']) if job['supervisor'] else None):
            raise ValueError('Supervisor identity is no longer live; refusing to signal another process')
        c.execute('UPDATE jobs SET stop_requested=1 WHERE id=?', (job_id,))
        store.audit(c, 'stop_requested', {'job': job_id})
    return {'job': job_id, 'stop_requested': True}


def start(settings, spec):
    """Start an owned supervisor. The CLI never directly signals stored PIDs."""
    if not isinstance(spec.get('argv'), list) or not spec['argv'] or not all(isinstance(v, str) for v in spec['argv']):
        raise ValueError('Explicit command arguments are required')
    for name in ('reserve_bytes', 'log_bytes'):
        if type(spec.get(name)) is not int or spec[name] <= 0:
            raise ValueError(name + ' must be a positive integer')
    for name in ('timeout_seconds', 'max_rss_bytes'):
        if spec.get(name) is not None and (type(spec[name]) is not int or spec[name] <= 0):
            raise ValueError(name + ' must be positive or unknown')
    if type(spec.get('termination_grace_seconds',2)) is not int or not 0<spec.get('termination_grace_seconds',2)<=120:
        raise ValueError('Termination grace must be an integer in 1..120 seconds')
    if spec['log_bytes'] > spec['reserve_bytes']:
        raise ValueError('Log allowance must fit in the declared job reservation')
    if spec.get('namespace'):
        if type(spec.get('namespace_reserve_bytes')) is not int or spec['namespace_reserve_bytes'] <= 0:
            raise ValueError('Namespace reservation must be positive')
        with CacheStore(settings).lease(spec['namespace'], 'namespace_check'):
            namespaces.check(CacheStore(settings), spec['namespace'], spec['fingerprint'])
    store = CacheStore(settings)
    job_id = 'job:' + object_hash({'nonce': uuid.uuid4().hex})
    spec = dict(spec, cwd=str(Path(spec.get('cwd', Path.cwd())).resolve()),
                storage_policy=settings.storage_policy, query_reserve_bytes=settings.query_reserve_bytes)
    if spec.get('evidence_run'):
        target=settings.data_dir/'evidence'/identifier(spec['evidence_run'])
        if target.exists() or target.is_symlink() or target.parent.is_symlink():
            raise ValueError('Evidence output must be a fresh owned run directory')
        spec['evidence_output']=str(target)
    with store.lease(job_id, 'job_start', reserve=spec['reserve_bytes'], writer=True) as token:
        path = store.create_directory(job_id, {'kind': spec['kind'], 'spec_sha256': object_hash(spec)})
        atomic_json(path / 'command.json', spec)
        store.seal(job_id, token)
        with store.locked() as c:
            c.execute('INSERT INTO jobs(id,spec,status) VALUES(?,?,?)', (job_id, canonical_json(spec), 'queued'))
        proc = subprocess.Popen([sys.executable, '-m', 'rdnascope.workers', str(settings.data_dir), str(settings.cache_dir), job_id],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        _job_update(store, job_id, supervisor=process_identity(proc.pid))
    return {'job': job_id, 'logs': str(path), 'supervisor_pid': proc.pid}


def wait(settings, job_id, deadline_seconds=None):
    deadline = time.monotonic() + deadline_seconds if deadline_seconds else None
    try:
        while True:
            result = status(settings, job_id)
            if result['status'] not in ('queued', 'running') and not result['supervisor_alive']:
                return result
            if result['status'] in ('queued', 'running') and not result['supervisor_alive']:
                raise ValueError('Worker disappeared; inspect retained logs and reconcile leases')
            if deadline is not None and time.monotonic() > deadline:
                raise TimeoutError('Managed job has not stopped within the wait deadline')
            time.sleep(.05)
    except KeyboardInterrupt:
        stop(settings, job_id)
        wait(settings, job_id, result['spec'].get('termination_grace_seconds',2)+15)
        raise


def _parent_death(expected_parent):
    # Called only in this single-threaded supervisor's child before exec.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != expected_parent:
        os._exit(125)


def _exit_info(proc):
    # Keep the leader waitable until its entire owned process group is stopped.
    # Its unreaped PID prevents reuse while group signals are sent.
    return os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)


def _kill_group(proc,grace=2):
    if proc is not None and proc.returncode is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + grace
        while _exit_info(proc) is None and time.monotonic() < deadline:
            time.sleep(.02)
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                pid, _ = os.waitpid(-proc.pid, os.WNOHANG)
                if pid == 0:time.sleep(.02)
            except ChildProcessError:
                break


def supervise(settings, job_id):
    # Adopt/reap orphaned descendants from this supervisor's commands only.
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError('Linux child-subreaper support is required')
    store = CacheStore(settings)
    job = status(settings, job_id)
    spec = job['spec']
    settings.storage_policy = spec['storage_policy']
    _job_update(store, job_id, supervisor=process_identity())
    canceled = False
    def cancel(signum, frame):
        nonlocal canceled
        canceled = True
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    proc, outcome, reason, error = None, 'failed', None, None
    peak_rss = 0
    started = time.monotonic()
    path = store.path(job_id)
    namespace = spec.get('namespace')
    namespace_touched = False
    with ExitStack() as stack:
        # Parent hands off its reservation before this lease starts.
        for attempt in range(100):
            try:
                job_token = stack.enter_context(store.lease(job_id, 'worker', reserve=spec['reserve_bytes'], writer=True))
                break
            except ValueError as exc:
                if 'busy' not in str(exc) or attempt == 99:
                    _job_update(store, job_id, status='failed', result={'reason': str(exc), 'child_started': False})
                    with store.locked() as c:
                        c.execute('INSERT OR IGNORE INTO refs VALUES(?,?)', (job_id, 'non-success-job-evidence'))
                    return
                time.sleep(.02)
        ns_token = None
        try:
            env = dict(os.environ)
            output_dir=Path(spec['evidence_output']) if spec.get('evidence_output') else path/'outputs'
            if spec.get('evidence_output'):
                if output_dir.parent.is_symlink():raise ValueError('Evidence root must not be a symlink')
                output_dir.parent.mkdir(parents=True,exist_ok=True)
                if output_dir.parent.stat().st_dev!=store.root.stat().st_dev:raise ValueError('This writer requires evidence/cache on the same filesystem for disk reservation')
                output_dir.mkdir(exist_ok=False)
            else:output_dir.mkdir(exist_ok=True)
            env['RDNASCOPE_JOB_OUTPUT']=str(output_dir)
            argv=[argument.replace('{output_dir}',str(output_dir)) for argument in spec['argv']] if spec.get('expand_output_dir') else spec['argv']
            frozen={}
            if spec.get('bound_inputs'):
                bound=path/'bound-inputs';bound.mkdir()
                for entry in spec['bound_inputs']:
                    source=Path(entry['path'])
                    if file_hash(source)!=entry['sha256']:raise ValueError('Bound adapter input changed before launch')
                    if source.stat().st_size>settings.max_json_bytes:raise ValueError('Bound helper input exceeds freeze budget')
                    destination=bound/(entry['sha256']+'-'+source.name)
                    if not destination.exists():shutil.copy2(source,destination)
                    if file_hash(destination)!=entry['sha256']:raise ValueError('Frozen adapter input mismatch')
                    frozen[str(source)]=str(destination)
                argv=[frozen.get(argument,argument) for argument in argv]
                atomic_json(bound/'manifest.json',{'sources':spec['bound_inputs'],'frozen_paths':frozen})
            atomic_json(path/'applied-command.json',{'argv':argv,'output_dir':str(output_dir),'cwd':spec['cwd']})
            if namespace:
                ns_token = stack.enter_context(store.lease(namespace, 'compiler_writer', reserve=spec['namespace_reserve_bytes'], writer=True))
                env.update(namespaces.check(store, namespace, spec['fingerprint']))
                (store.path(namespace) / 'data').mkdir(exist_ok=True)
                namespace_touched = True
            scratch = path / 'scratch'
            scratch.mkdir()
            env['TMPDIR'] = str(scratch)
            if spec.get('trace'):
                trace = spec['trace']
                if file_hash(Path(trace['path'])) != trace['sha256'] or file_hash(Path(spec['argv'][0])) != spec['tool']['binary_sha256']:
                    raise ValueError('Trace/tool changed before service launch')
            if status(settings, job_id)['stop_requested'] or canceled:
                reason = 'canceled_before_launch'
                outcome = 'canceled'
            else:
                parent_pid = os.getpid()
                with (path / 'stdout.log').open('wb') as out, (path / 'stderr.log').open('wb') as err:
                    proc = subprocess.Popen(argv, cwd=spec['cwd'], env=env,
                                            stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                            start_new_session=True, preexec_fn=lambda: _parent_death(parent_pid))
                    child = process_identity(proc.pid)
                    _job_update(store, job_id, child=child, status='running')
                    while _exit_info(proc) is None:
                        now = time.monotonic()
                        measured = memory(child)['rss_bytes'] or 0
                        peak_rss = max(peak_rss, measured)
                        if canceled or status(settings, job_id)['stop_requested']:
                            reason = 'stop_requested';outcome = 'canceled';break
                        if spec.get('timeout_seconds') and now - started > spec['timeout_seconds']:
                            reason = 'timeout';outcome = 'timeout';break
                        if spec.get('max_rss_bytes') and measured > spec['max_rss_bytes']:
                            reason = 'rss_limit_exceeded';outcome = 'budget_blocked';break
                        if (path/'stdout.log').stat().st_size + (path/'stderr.log').stat().st_size > spec['log_bytes']:
                            reason = 'log_limit_exceeded';outcome = 'budget_blocked';break
                        checks = [store.check_reservation(job_token)]
                        if spec.get('evidence_output') and snapshot(output_dir)['bytes']>spec['reserve_bytes']:
                            reason='evidence_output_budget_exceeded';outcome='budget_blocked';break
                        if ns_token: checks.append(store.check_reservation(ns_token))
                        if any(check['status'] != 'pass' for check in checks):
                            reason = 'storage_budget_exceeded';outcome = 'budget_blocked';break
                        time.sleep(.1)
                    if reason is None:
                        info = _exit_info(proc)
                        outcome = 'passed' if info.si_code == os.CLD_EXITED and info.si_status == 0 else 'failed'
                        reason = 'command_exit'
        except Exception as exc:
            error = str(exc);reason = 'worker_error';outcome = 'failed'
        finally:
            _kill_group(proc,spec.get('termination_grace_seconds',2))
            if outcome == 'passed':
                try:
                    checks = [store.check_reservation(job_token)]
                    if namespace_touched: checks.append(store.check_reservation(ns_token))
                    if any(check['status'] != 'pass' for check in checks):
                        outcome = 'budget_blocked';reason = 'storage_budget_exceeded_at_exit'
                    if spec.get('evidence_output') and snapshot(output_dir)['bytes']>spec['reserve_bytes']:
                        outcome='budget_blocked';reason='evidence_output_budget_exceeded_at_exit'
                except (ValueError,OSError) as exc:
                    outcome = 'failed';reason = 'unsafe_worker_output';error = str(exc)
            # Scratch belongs to this job. rmtree uses fd-based symlink protection.
            scratch = path / 'scratch'
            scratch_cleaned = False
            if scratch.is_symlink() or scratch.is_file():
                scratch.unlink();scratch_cleaned = True
                outcome='failed';reason='scratch_directory_replaced'
            elif scratch.exists() and shutil.rmtree.avoids_symlink_attacks:
                try:shutil.rmtree(scratch);scratch_cleaned = True
                except OSError as exc:error=str(exc);outcome='failed';reason='scratch_cleanup_failed'
            truncated = False
            logs = {}
            remaining_log_bytes = spec['log_bytes']
            for name in ('stderr.log', 'stdout.log'):
                log = path / name
                if log.exists() or log.is_symlink():
                    try:
                        fd=os.open(log,os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
                        with os.fdopen(fd,'rb') as stream:
                            s=os.fstat(stream.fileno())
                            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=os.getuid():
                                raise ValueError('Worker log is not a private regular file')
                            if s.st_size>remaining_log_bytes:
                                os.ftruncate(stream.fileno(),remaining_log_bytes);truncated=True
                            size=os.fstat(stream.fileno()).st_size
                            logs[name]={'bytes':size,'sha256':hashlib.file_digest(stream,'sha256').hexdigest()}
                            remaining_log_bytes-=size
                    except (ValueError,OSError) as exc:
                        outcome='failed';reason='unsafe_log_output';error=str(exc)
            result = {'outcome': outcome, 'reason': reason, 'error': error,
                      'returncode': proc.returncode if proc else None, 'scratch_cleaned': scratch_cleaned,
                      'elapsed_seconds': time.monotonic() - started, 'peak_child_rss_bytes': peak_rss,
                      'log_truncated': truncated, 'logs': logs,
                      'child_live_after_cleanup': bool(proc and process_alive(child))}
            result['process_cleanup_passed']=not result['child_live_after_cleanup'] and scratch_cleaned
            if spec.get('evidence_output'):
                try:result['evidence_output']={'path':spec['evidence_output'],**snapshot(Path(spec['evidence_output']),True),'gc_policy':'external_evidence_never_deleted'}
                except (ValueError,OSError) as exc:result['evidence_output']={'path':spec['evidence_output'],'status':'unknown_or_incomplete','error':str(exc)}
            if truncated and outcome == 'passed':
                outcome = result['outcome'] = 'budget_blocked';result['reason'] = 'log_limit_exceeded_at_exit'
            if spec.get('trace'):
                try:result['input_hash_preserved'] = file_hash(Path(spec['trace']['path'])) == spec['trace']['sha256']
                except OSError:result['input_hash_preserved'] = False
                if not result['input_hash_preserved']:
                    outcome = result['outcome'] = 'failed';result['reason'] = 'input_hash_changed'
            if namespace_touched:
                try:store.seal(namespace, ns_token, 'ready' if outcome == 'passed' else 'quarantined')
                except (ValueError,OSError) as exc:
                    result['namespace_seal_error'] = str(exc);outcome = result['outcome'] = 'failed'
            atomic_json(path / 'result.json', result)
            try:store.seal(job_id, job_token)
            except (ValueError,OSError) as exc:
                result['job_seal_error'] = str(exc);outcome = result['outcome'] = 'failed'
            _job_update(store, job_id, status=outcome, result=result)
            if outcome != 'passed':
                with store.locked() as c:
                    c.execute('INSERT OR IGNORE INTO refs VALUES(?,?)', (job_id, 'non-success-job-evidence'))
                    if namespace_touched:c.execute('INSERT OR IGNORE INTO refs VALUES(?,?)', (namespace, 'failed-job:' + job_id))


if __name__ == '__main__':
    s = Settings(data_dir=Path(sys.argv[1]), cache_dir=Path(sys.argv[2]))
    supervise(s, sys.argv[3])

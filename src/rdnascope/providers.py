"""Read-only native ROCm/Perfetto and generic Chrome providers."""
from collections import defaultdict
import csv
import io
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import tempfile
import time

from .contracts import digest as file_hash, load_json as read_json
from .storage import local_path, sqlite_readonly


def ns(value, unit):
    if type(value) not in (int, float) or unit not in ('ns', 'us', 'ms', 's'):
        raise ValueError('Invalid timestamp or unit')
    factor = {'ns': 1, 'us': 1000, 'ms': 1000000, 's': 1000000000}[unit]
    result = value * factor
    if not __import__('math').isfinite(result):
        raise ValueError('Non-finite timestamp')
    return round(result)

def quote(name):
    return '"' + name.replace('"', '""') + '"'


def bounded_process(argv, timeout, max_output=8 * 1024 * 1024):
    """Limit query output on disk as well as memory; reap only this child group."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        p = subprocess.Popen(argv, stdout=out, stderr=err, start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while p.poll() is None:
                if time.monotonic() > deadline:
                    raise TimeoutError('Offline query exceeded time budget')
                if os.fstat(out.fileno()).st_size > max_output or os.fstat(err.fileno()).st_size > 256 * 1024:
                    raise ValueError('Offline query exceeded output budget')
                time.sleep(.02)
            if out.tell() > max_output or err.tell() > 256 * 1024:
                raise ValueError('Offline query exceeded output budget')
            out.seek(0); err.seek(0)
            stdout, stderr = out.read().decode(), err.read().decode()
            if p.returncode:
                raise ValueError(f'Offline tool exited {p.returncode}: {stderr[-2000:]}')
            return stdout, stderr
        finally:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.wait(timeout=5)


def provider_info(provider, settings):
    info = {'name': provider, 'contract_version': 1}
    if provider == 'pftrace':
        if not settings.trace_processor:
            raise ValueError('PFTrace requires an explicit tools.trace_processor path in the selected TOML profile; no tool is downloaded automatically')
        binary = Path(settings.trace_processor)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError('Configured Trace Processor is not executable')
        version, _ = bounded_process([str(binary), '--version'], min(10, settings.timeout_seconds), 32768)
        info.update(binary_sha256=file_hash(binary), version=version.strip())
    return info


def row(identity, artifact, locator, name, category, start=None, duration=None, process=None, **extra):
    mapped = next((r['rank'] for r in identity['ranks'] if process is not None and r['process_id'] == process), None)
    native_rank = identity['semantics']['native_rank'] if artifact['format'] == 'chrome' else None
    result = {'event_id': artifact['artifact_id'] + '#' + locator, 'artifact_id': artifact['artifact_id'],
              'name': name, 'category': category, 'start_ns': str(start) if start is not None else None,
              'duration_ns': str(duration) if duration is not None else None,
              'process_id': process, 'rank': mapped if mapped is not None else native_rank,
              'request': None, 'phase': None, 'token': None, 'graph': None,
              'clock_domain': identity['clock']['domain'] if identity['clock']['domain'] != 'unknown' else artifact['artifact_id'],
              'association': 'inferred' if mapped is not None or native_rank is not None else 'unmapped'}
    result.update(extra)
    return result


def rocpd_specs(c):
    names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    suffixes = [n[len('rocpd_kernel_dispatch_'):] for n in names if n.startswith('rocpd_kernel_dispatch_')]
    if not suffixes:
        raise ValueError('SQLite input is not a supported rocpd database')
    specs = []
    for suffix in sorted(suffixes):
        def t(base):
            return quote(base + '_' + suffix)
        proc = t('rocpd_info_process')
        sym = t('rocpd_info_kernel_symbol')
        string = t('rocpd_string')
        event = t('rocpd_event')
        for base, category in [('rocpd_kernel_dispatch', 'kernel_dispatch'), ('rocpd_region', 'region'),
                               ('rocpd_graph_launch', 'graph_execution'), ('rocpd_memory_copy', 'memory_copy'),
                               ('rocpd_hip_event', 'hip_event')]:
            table_name = base + '_' + suffix
            if table_name not in names:
                continue
            table = quote(table_name)
            cols = {r[1] for r in c.execute('PRAGMA table_info(' + table + ')')}
            bad = c.execute(f"SELECT count(*) FROM {table} WHERE typeof(start)!='integer' OR typeof(end)!='integer' OR end<start").fetchone()[0]
            if bad:
                raise ValueError('rocpd contains invalid or negative timestamp intervals')
            category_expr = "'" + category + "'"
            joins = f' LEFT JOIN {proc} p ON r.pid=p.id'
            correlation = 'NULL'
            if 'event_id' in cols and 'rocpd_event_' + suffix in names:
                joins += f' LEFT JOIN {event} evt ON r.event_id=evt.id'
                correlation = 'evt.correlation_id'
            if category == 'kernel_dispatch':
                joins += f' LEFT JOIN {sym} s ON r.kernel_id=s.id'
                name = 'coalesce(s.display_name,s.kernel_name,\'unknown\')'
            elif category == 'graph_execution':
                name = "'[Graph Execution]'"
            else:
                joins += f' LEFT JOIN {string} s ON r.name_id=s.id'
                name = "coalesce(s.string,'unknown')"
                if category == 'region':
                    joins += f' LEFT JOIN {event} e ON r.event_id=e.id LEFT JOIN {string} cat ON e.category_id=cat.id'
                    category_expr = "CASE WHEN cat.string LIKE 'HIP_%' THEN 'hip_api' WHEN cat.string LIKE 'MARKER_%' THEN 'marker_api' ELSE coalesce(cat.string,'unknown') END"
            extras = ','.join('r.' + x if x in cols else 'NULL AS ' + x for x in ('queue_id', 'stream_id', 'graph_exec_id', 'graph_node_id', 'agent_id', 'dispatch_id', 'event_id', 'tid'))
            specs.append({'table': table_name, 'query': f'SELECT r.id,p.pid process_id,{name} name,{category_expr} category,r.start,r.end,{extras},{correlation} correlation_id FROM {table} r {joins}'})
    return specs


def rocpd(artifacts, identity, view, settings, limit, offset):
    result = []
    remaining_offset = offset
    for a in artifacts:
        c = sqlite_readonly(local_path(a['uri']))
        deadline = time.monotonic() + settings.timeout_seconds
        c.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        try:
            for spec in rocpd_specs(c):
                if view == 'kernels' and not spec['table'].startswith('rocpd_kernel_dispatch_'):
                    continue
                q = spec['query']
                if view == 'summary':
                    for r in c.execute(f'SELECT category,count(*) n,sum(end-start) duration_ns FROM ({q}) GROUP BY category ORDER BY category'):
                        result.append({'artifact_id': a['artifact_id'], 'category': r['category'], 'count': r['n'],
                                       'duration_ns': str(r['duration_ns'] or 0), 'duration_semantics': 'sum_intervals_not_wall'})
                else:
                    total = c.execute(f'SELECT count(*) FROM ({q})').fetchone()[0]
                    if remaining_offset >= total:
                        remaining_offset -= total
                        continue
                    for r in c.execute(q + ' ORDER BY r.id LIMIT ? OFFSET ?', (limit + 1 - len(result), remaining_offset)):
                        result.append(row(identity, a, spec['table'] + '/id=' + str(r['id']), r['name'], r['category'],
                                          r['start'], r['end'] - r['start'], r['process_id'],
                                          queue=r['queue_id'], stream=r['stream_id'], graph=r['graph_exec_id'],
                                          graph_node=r['graph_node_id'], agent=r['agent_id'],
                                          dispatch_id=r['dispatch_id'], correlation_id=r['correlation_id'],
                                          correlation_scope=a['artifact_id'] + '/rocpd_event.correlation_id',
                                          native_event_id=r['event_id'], native_thread_ref=r['tid']))
                    remaining_offset = 0
                    if len(result) > limit:
                        return result
        except sqlite3.Error as exc:
            raise ValueError('Unsupported, malformed or timed-out rocpd schema: ' + str(exc)) from exc
        finally:
            c.close()
    return result[offset:offset + limit + 1] if view == 'summary' else result


def perfetto(artifacts, identity, view, settings, limit, offset):
    result = []
    remaining = offset
    for a in artifacts:
        trace = local_path(a['uri'])
        if view == 'summary':
            sql = ("SELECT CASE WHEN name='[Graph Execution]' THEN 'graph_execution' ELSE category END category,"
                   "count(*) n,sum(dur) duration_ns,min(dur) minimum_ns FROM slice GROUP BY 1 ORDER BY 1")
        else:
            where = " WHERE category='kernel_dispatch'" if view == 'kernels' else ''
            count_sql = 'SELECT count(*) n FROM slice' + where
            count_out, _ = bounded_process([settings.trace_processor, 'query', '--no-agent', '--format', 'csv', str(trace), count_sql], settings.timeout_seconds)
            total = int(next(csv.DictReader(io.StringIO(count_out)))['n'])
            if remaining >= total:
                remaining -= total
                continue
            sql = ("SELECT s.id,s.name,CASE WHEN s.name='[Graph Execution]' THEN 'graph_execution' ELSE s.category END category,"
                   "s.ts,s.dur,s.track_id,coalesce(p1.pid,p2.pid) process_id,"
                   "extract_arg(s.arg_set_id,'debug.corr_id') correlation_id,"
                   "extract_arg(s.arg_set_id,'debug.graph_exec_id') graph_exec_id,"
                   "extract_arg(s.arg_set_id,'debug.graph_node_id') graph_node_id,"
                   "extract_arg(s.arg_set_id,'debug.queue') queue_id,"
                   "extract_arg(s.arg_set_id,'debug.stream_id') stream_id "
                   "FROM slice s LEFT JOIN thread_track tt ON s.track_id=tt.id "
                   "LEFT JOIN thread th ON tt.utid=th.utid LEFT JOIN process p1 ON th.upid=p1.upid "
                   "LEFT JOIN process_track pt ON s.track_id=pt.id LEFT JOIN process p2 ON pt.upid=p2.upid" +
                   where.replace('category=', 's.category=') + ' ORDER BY s.id LIMIT ' + str(limit + 1 - len(result)) + ' OFFSET ' + str(remaining))
            remaining = 0
        argv = [settings.trace_processor, 'query', '--no-agent', '--format', 'csv', str(trace), sql]
        stdout, _ = bounded_process(argv, settings.timeout_seconds)
        for r in csv.DictReader(io.StringIO(stdout)):
            if view == 'summary':
                if int(r['minimum_ns']) < 0:
                    raise ValueError('Incomplete/open Perfetto slices are not qualified intervals')
                result.append({'artifact_id': a['artifact_id'], 'category': r['category'], 'count': int(r['n']),
                               'duration_ns': r['duration_ns'], 'duration_semantics': 'sum_intervals_not_wall'})
            else:
                start, duration = int(r['ts']), int(r['dur'])
                if duration < 0:
                    raise ValueError('Incomplete/open Perfetto slices are not qualified intervals')
                def number(key):
                    return None if r[key] in ('[NULL]', '') else int(r[key])
                result.append(row(identity, a, 'slice/' + r['id'], r['name'], r['category'], start, duration,
                                  number('process_id'), track=r['track_id'], correlation_id=number('correlation_id'),
                                  correlation_scope=a['artifact_id'] + '/perfetto.debug.corr_id',
                                  graph=number('graph_exec_id'),graph_node=number('graph_node_id'),
                                  queue=number('queue_id'),stream=number('stream_id'),
                                  locator_scope='artifact_and_trace_processor_build'))
                if len(result) > limit:
                    return result
    return result[offset:offset + limit + 1] if view == 'summary' else result


def json_query(artifacts, identity, provider, view, settings, limit, offset):
    if provider != 'chrome':
        raise ValueError('Only generic Chrome X events are supported')
    rows=[]; groups=defaultdict(lambda:[0,0]); index=0
    deadline=time.monotonic()+settings.timeout_seconds
    for a in artifacts:
        data=read_json(local_path(a['uri']),settings.max_json_bytes)
        if not isinstance(data,dict) or not isinstance(data.get('traceEvents'),list):
            raise ValueError('Chrome traceEvents array required')
        for i,event in enumerate(data['traceEvents']):
            if time.monotonic()>deadline:
                raise TimeoutError('Chrome query exceeded budget')
            if not isinstance(event,dict):
                raise ValueError('Chrome event must be an object')
            if event.get('ph')!='X':
                continue
            unit=identity['semantics']['time_unit']
            start,duration=ns(event['ts'],unit),ns(event['dur'],unit)
            if duration<0:
                raise ValueError('Negative Chrome duration')
            cat=event.get('cat','unknown')
            category='kernel_dispatch' if cat in ('kernel','gpu_kernel','kernel_dispatch') else cat
            args=event.get('args',{})
            if not isinstance(args,dict):
                raise ValueError('Chrome args must be an object')
            item=row(identity,a,'traceEvents/'+str(i),event.get('name','unknown'),category,start,duration,event.get('pid'),
                     request=args.get('request'),phase=args.get('phase'),token=args.get('position'),graph=args.get('graph'),
                     original_time={'ts':event['ts'],'dur':event['dur'],'unit':unit},original_category=cat)
            if view=='summary':
                group=groups[(a['artifact_id'],category)];group[0]+=1;group[1]+=duration
                if len(groups)>4096:raise ValueError('Too many summary groups')
                continue
            if view=='kernels' and category!='kernel_dispatch':continue
            if index>=offset:rows.append(item)
            index+=1
            if len(rows)>limit:return rows
    if view=='summary':
        return [{'artifact_id':a,'category':cat,'count':count,'duration_ns':str(duration),
                 'duration_semantics':'sum_intervals_not_wall'} for (a,cat),(count,duration) in sorted(groups.items())][offset:offset+limit+1]
    return rows

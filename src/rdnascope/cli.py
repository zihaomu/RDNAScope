"""CPU-only CLI. Registration and query APIs cannot launch a GPU workload."""
import argparse
import json
from pathlib import Path
import platform
import sqlite3
import sys

from . import __version__
from .core import SCHEMA_NAMES, Settings, atomic_json, file_hash, minimal_identity, read_json, schema, validate
from .query import execute
from .storage import Registry
from .lifecycle import CacheStore
from . import namespaces, workers, services
from . import workflow_cli


def parser():
    p = argparse.ArgumentParser(description='RDNAScope: offline evidence and explicit managed-cache lifecycle')
    p.add_argument('--version', action='version', version='rdnascope ' + __version__)
    p.add_argument('--config', type=Path)
    p.add_argument('--data-dir', type=Path)
    p.add_argument('--cache-dir', type=Path)
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('doctor')
    q = sub.add_parser('identity');q.add_argument('--run', required=True);q.add_argument('--experiment');q.add_argument('--output', type=Path)
    q = sub.add_parser('schema');q.add_argument('name', choices=SCHEMA_NAMES)
    q = sub.add_parser('validate');q.add_argument('name', choices=SCHEMA_NAMES);q.add_argument('input',type=Path)
    q = sub.add_parser('register');q.add_argument('inputs',nargs='*',type=Path);q.add_argument('--run');q.add_argument('--identity',type=Path)
    q.add_argument('--format',default='auto',choices=['auto','rocpd','pftrace','http','chrome','tlp-legacy'])
    q.add_argument('--manifest',type=Path,help='Explicit identity+input descriptor; paths relative to this manifest')
    q = sub.add_parser('inspect');q.add_argument('run')
    q = sub.add_parser('query');q.add_argument('run');q.add_argument('--view',default='summary',choices=['summary','events','kernels','metrics','phases','collectives','coverage','provenance'])
    q.add_argument('--provider',default='auto',choices=['auto','rocpd','pftrace','http','chrome','legacy'])
    q.add_argument('--limit',type=int,default=100);q.add_argument('--offset',type=int,default=0);q.add_argument('--no-cache',action='store_true')
    q.add_argument('--artifact',action='append',help='Select registered content IDs to avoid combining related representations')
    sub.add_parser('storage-stats')
    cache = sub.add_parser('cache').add_subparsers(dest='cache_action', required=True)
    cache.add_parser('list')
    q=cache.add_parser('preflight');q.add_argument('--reserve-bytes',type=int,default=0)
    for action in ('pin','unpin'):
        q=cache.add_parser(action);q.add_argument('item');q.add_argument('--reference',required=True)
    q=cache.add_parser('gc');q.add_argument('--older-than-seconds',type=int);q.add_argument('--reclaim-bytes',type=int)
    q.add_argument('--output',type=Path);q.add_argument('--execute',action='store_true');q.add_argument('--plan',type=Path)
    cache.add_parser('reconcile')
    q=cache.add_parser('namespace');q.add_argument('fingerprint',type=Path);q.add_argument('--cold-session')
    q=cache.add_parser('run');q.add_argument('--namespace',required=True);q.add_argument('--fingerprint',type=Path,required=True)
    q.add_argument('--reserve-bytes',type=int,required=True);q.add_argument('--timeout-seconds',type=int,required=True)
    q.add_argument('--max-rss-bytes',type=int);q.add_argument('command',nargs=argparse.REMAINDER)
    svc=sub.add_parser('service').add_subparsers(dest='service_action',required=True)
    q=svc.add_parser('start');q.add_argument('--run',required=True);q.add_argument('--artifact',required=True);q.add_argument('--port',type=int,required=True)
    idle=q.add_mutually_exclusive_group(required=True);idle.add_argument('--idle-seconds',type=int);idle.add_argument('--keep',action='store_true')
    q.add_argument('--max-rss-bytes',type=int);q.add_argument('--max-seconds',type=int)
    svc.add_parser('list')
    q=svc.add_parser('status');q.add_argument('job')
    q=svc.add_parser('stop');q.add_argument('job')
    workflow_cli.extend(sub)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        s = Settings(args.config, args.data_dir, args.cache_dir)
        registry = Registry(s)
        if args.action == 'doctor':
            result = {'version':__version__, 'python':platform.python_version(), 'scope':'offline_only_no_gpu_probe',
                      'paths':{'data':str(s.data_dir),'cache':str(s.cache_dir)},
                      'providers':{'rocpd':True,'http':True,'chrome':True,'legacy':True,
                                   'pftrace_configured':bool(s.trace_processor)},
                      'trace_processor':{'path':s.trace_processor,'exists':bool(s.trace_processor and Path(s.trace_processor).is_file())},
                      'gpu_collection':'explicit_guarded_adapter_required; per-profile qualification only','performance_qualification':'unknown',
                      'legacy_bridge_configured':bool(s.legacy_executable)}
            result['storage_policy']=s.storage_policy
            result['lifecycle']='R2_managed_cache_only_explicit_gc'
        elif args.action == 'identity':
            result = minimal_identity(args.run, args.experiment)
            if args.output:atomic_json(args.output,result)
        elif args.action == 'schema':
            result = schema(args.name)
        elif args.action == 'validate':
            validate(args.name,read_json(args.input,s.max_json_bytes));result={'status':'valid','schema':args.name,'schema_version':1}
        elif args.action == 'register':
            if args.manifest:
                if args.inputs or args.identity or args.run or args.format!='auto':
                    raise ValueError('--manifest cannot be combined with positional inputs/run/identity/format')
                m=read_json(args.manifest,s.max_json_bytes)
                if not isinstance(m,dict) or set(m)!={'schema_version','identity','inputs'} or m['schema_version']!=1 or not isinstance(m['inputs'],list):
                    raise ValueError('Registration manifest requires schema_version=1, identity and inputs')
                entries=[]
                for e in m['inputs']:
                    if not isinstance(e,dict) or not isinstance(e.get('path'),str):
                        raise ValueError('Registration inputs must be objects with a path string')
                    path=Path(e['path']).expanduser()
                    entries.append(dict(e,path=str((args.manifest.resolve().parent/path).resolve() if not path.is_absolute() else path)))
                result=registry.register(m['identity'],entries)
            else:
                if not args.run or not args.inputs:
                    raise ValueError('register requires --run and explicit inputs, or --manifest')
                identity=read_json(args.identity,s.max_json_bytes) if args.identity else minimal_identity(args.run)
                if identity['run_id']!=args.run:raise ValueError('Identity run_id differs from --run')
                result=registry.register(identity,[{'path':str(p),'format':args.format} for p in args.inputs])
        elif args.action == 'inspect':
            result=registry.inspect(args.run)
        elif args.action == 'query':
            result=execute(s,args.run,args.view,args.provider,args.limit,args.offset,not args.no_cache,args.artifact)
        elif args.action == 'cache':
            store=CacheStore(s)
            if args.cache_action=='list':result=store.inventory()
            elif args.cache_action=='preflight':result=store.preflight(args.reserve_bytes)
            elif args.cache_action in ('pin','unpin'):result=store.reference(args.item,args.reference,args.cache_action=='unpin')
            elif args.cache_action=='reconcile':result=store.reconcile()
            elif args.cache_action=='namespace':result=namespaces.create(s,read_json(args.fingerprint,s.max_json_bytes),args.cold_session)
            elif args.cache_action=='gc':
                if args.execute:
                    if not args.plan or args.output or args.older_than_seconds is not None or args.reclaim_bytes is not None:
                        raise ValueError('GC execution requires only --execute --plan with an unchanged preview')
                    result=store.gc_apply(read_json(args.plan,s.max_json_bytes))
                else:
                    if args.plan:raise ValueError('--plan is only valid with --execute')
                    if args.output and (args.output.exists() or args.output.is_symlink() or args.output.resolve().is_relative_to(s.cache_dir)):
                        raise ValueError('GC preview output must be a new file outside the managed cache')
                    result=store.gc_preview(args.older_than_seconds,args.reclaim_bytes)
                    if args.output:atomic_json(args.output,result)
            else:
                command=args.command[1:] if args.command[:1]==['--'] else args.command
                spec={'kind':'command','argv':command,'namespace':args.namespace,'fingerprint':read_json(args.fingerprint,s.max_json_bytes),
                      'namespace_reserve_bytes':args.reserve_bytes,'reserve_bytes':2*1024*1024,'log_bytes':1024*1024,
                      'timeout_seconds':args.timeout_seconds,'max_rss_bytes':args.max_rss_bytes}
                started=workers.start(s,spec);result=workers.wait(s,started['job'])
        elif args.action == 'service':
            if args.service_action=='start':result=services.start(s,args.run,args.artifact,args.port,args.idle_seconds,args.keep,args.max_rss_bytes,args.max_seconds)
            elif args.service_action=='list':result=workers.status(s)
            elif args.service_action=='status':result=workers.status(s,args.job)
            else:
                result=workers.stop(s,args.job)
                if result['stop_requested']:result=workers.wait(s,args.job,10)
        elif args.action in workflow_cli.ACTIONS:
            result=workflow_cli.dispatch(s,args)
        else:
            result=registry.stats()
        print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False))
        if args.action=='cache' and args.cache_action=='run' and result['status']!='passed':return 2
        if args.action=='cache' and args.cache_action=='preflight' and result['status']=='blocked':return 2
        if args.action=='workload' and result.get('status') in ('resource_blocked','failed','incomplete'):return 2
        if args.action=='capture' and result.get('status')=='failed':return 2
        return 0
    except KeyboardInterrupt:
        print(json.dumps({'status':'canceled','message':'Owned job stop requested; logs retained'}),file=sys.stderr)
        return 130
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error,TimeoutError) as exc:
        print(json.dumps({'status':'error','message':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2

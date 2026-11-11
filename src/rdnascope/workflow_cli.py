"""Stable evidence/qualification/benchmark/analysis/experiment command groups."""
from pathlib import Path

from .core import atomic_json, read_json
from .records import Records
from . import capabilities, benchmark, analysis, experiments, workloads, resources, ui

ACTIONS={'records','capabilities','capture','bench','reference','semantics','analyze','experiment','workload','devices','kb','ui'}


def extend(sub):
    q=sub.add_parser('devices');q.add_argument('--physical-gpus',type=int,nargs='+')
    q=sub.add_parser('ui');q.add_argument('ui_action',choices=['locate']);q.add_argument('finding');q.add_argument('--pftrace');q.add_argument('--port',type=int,default=9001)
    rec=sub.add_parser('records').add_subparsers(dest='record_action',required=True)
    from .records import KINDS
    for action in ('list','get','verify'):
        q=rec.add_parser(action);q.add_argument('kind',choices=KINDS)
        if action!='list':q.add_argument('id')
    cap=sub.add_parser('capabilities').add_subparsers(dest='cap_action',required=True)
    cap.add_parser('list')
    q=cap.add_parser('register');q.add_argument('input',type=Path);q.add_argument('--id',required=True)
    q=cap.add_parser('resolve');q.add_argument('context',type=Path)
    q=sub.add_parser('capture');q.add_argument('capture_action',choices=['audit']);q.add_argument('run')
    q.add_argument('--contract',required=True,type=Path);q.add_argument('--pftrace',required=True);q.add_argument('--output',type=Path)
    bench=sub.add_parser('bench').add_subparsers(dest='bench_action',required=True)
    q=bench.add_parser('contract');q.add_argument('input',type=Path);q.add_argument('--id',required=True);q.add_argument('--evidence',type=Path)
    q=bench.add_parser('ingest');q.add_argument('spec',type=Path);q.add_argument('--id',required=True)
    q=bench.add_parser('aa');q.add_argument('measurements',nargs='+')
    q=bench.add_parser('compare');q.add_argument('--baseline',action='append',required=True);q.add_argument('--candidate',action='append',required=True)
    ref=sub.add_parser('reference').add_subparsers(dest='reference_action',required=True)
    q=ref.add_parser('register');q.add_argument('input',type=Path);q.add_argument('--id',required=True);q.add_argument('--evidence',type=Path)
    q=ref.add_parser('match');q.add_argument('id');q.add_argument('context',type=Path)
    q=sub.add_parser('semantics');q.add_argument('semantic_action',choices=['register']);q.add_argument('input',type=Path);q.add_argument('--id',required=True)
    q=sub.add_parser('analyze');q.add_argument('run');q.add_argument('--output',required=True,help='Immutable finding/case ID prefix')
    q.add_argument('--provider',default='auto',choices=['auto','rocpd','pftrace','chrome','http','legacy']);q.add_argument('--artifact',action='append')
    q.add_argument('--map');q.add_argument('--reference',action='append')
    q.add_argument('--measurement',action='append')
    q=sub.add_parser('experiment');q.add_argument('experiment_action',choices=['evaluate']);q.add_argument('spec',type=Path);q.add_argument('--id',required=True)
    work=sub.add_parser('workload').add_subparsers(dest='workload_action',required=True)
    q=work.add_parser('fixture');q.add_argument('--contract',required=True);q.add_argument('--prefix',required=True);q.add_argument('--phase',choices=['aa','compare'],default='aa')
    q=work.add_parser('run');q.add_argument('plan',type=Path)
    kb=sub.add_parser('kb').add_subparsers(dest='kb_action',required=True)
    q=kb.add_parser('search');q.add_argument('query')
    q=kb.add_parser('archive');q.add_argument('input',type=Path);q.add_argument('--id',required=True);q.add_argument('--evidence',type=Path)
    q=kb.add_parser('verify');q.add_argument('id')


def dispatch(settings,args):
    store=Records(settings)
    read=lambda path:read_json(path,settings.max_json_bytes)
    if args.action=='devices':return resources.discover(settings,args.physical_gpus)
    if args.action=='ui':return ui.locate(settings,args.finding,args.pftrace,args.port)
    if args.action=='records':
        if args.record_action=='list':return {'records':store.list(args.kind)}
        return store.get(args.kind,args.id) if args.record_action=='get' else store.verify_tree(args.kind,args.id)
    if args.action=='capabilities':
        if args.cap_action=='list':return {'records':[store.get('capability',r['id']) for r in store.list('capability')]}
        if args.cap_action=='register':return capabilities.register(settings,args.id,read(args.input))
        return capabilities.resolve(settings,read(args.context))
    if args.action=='capture':
        result=capabilities.audit(settings,args.run,read(args.contract),args.pftrace)
        if args.output:
            if args.output.exists() or args.output.resolve().is_relative_to(settings.cache_dir):raise ValueError('Audit output must be a new file outside cache')
            atomic_json(args.output,result)
        return result
    if args.action=='bench':
        if args.bench_action=='contract':return benchmark.register_contract(settings,args.id,read(args.input),read(args.evidence) if args.evidence else None)
        if args.bench_action=='ingest':
            s=read(args.spec)
            return benchmark.ingest(settings,args.id,s['contract_id'],s['adapter'],s['input_ref'],s['boot'],s['arm'],s['context'],s.get('oracle_ref'),s.get('resource_ref'))
        if args.bench_action=='aa':return benchmark.aa(settings,args.measurements)
        return benchmark.compare(settings,args.baseline,args.candidate)
    if args.action=='reference':
        if args.reference_action=='register':return benchmark.register_reference(settings,args.id,read(args.input),read(args.evidence) if args.evidence else None)
        return benchmark.reference_match(settings,args.id,read(args.context))
    if args.action=='semantics':return analysis.register_map(settings,args.id,read(args.input))
    if args.action=='analyze':return analysis.analyze(settings,args.run,args.output,args.provider,args.artifact,args.map,args.reference,args.measurement)
    if args.action=='experiment':return experiments.evaluate(settings,args.id,read(args.spec))
    if args.action=='workload':
        if args.workload_action=='fixture':return workloads.fixture(settings,args.contract,args.prefix,args.phase)
        return workloads.external(settings,read(args.plan))
    if args.kb_action=='verify':return store.verify_tree('case',args.id)
    if args.kb_action=='archive':
        body=read(args.input)
        for child in body['records']:
            verified=store.verify_tree(child['kind'],child['id'])
            if verified['record_sha256']!=child['record_sha256']:raise ValueError('Archived case record SHA mismatch')
        return store.add('case',args.id,body,read(args.evidence) if args.evidence else None)
    terms=args.query.casefold().split();found=[]
    for entry in store.list('case'):
        record=store.get('case',entry['id']);body=record['body'];text=(body['title']+' '+body['observation']).casefold()
        if all(term in text for term in terms):found.append({'id':entry['id'],'record_sha256':entry['record_sha256'],'status':body['status'],'title':body['title']})
    return {'cases':found,'method':'lexical; statuses/old failures retained'}

"""Evidence-scoped capabilities and offline native conservation qualification."""
from collections import Counter
import sqlite3

from .core import validate
from .records import Records, evidence
from .query import execute
from .storage import Registry, local_path, sqlite_readonly

CONTEXT_KEYS=('device_model','gfx','rocm','hip','driver','runtime_digest','native_digest','backend','tool_sha256','mode','world','device_set','workload_revision')


def register(settings,name,body):
    validate('capability',body)
    refs=[]
    for feature,value in body['features'].items():
        if value['status'] in ('qualified','conditional','failed','unsupported'):
            if not value['scope'].strip() or not value['evidence']:
                raise ValueError('Qualified/conditional capabilities require explicit scope and evidence')
            if body['basis'] in ('declaration','synthetic'):
                raise ValueError('Declaration/CPU synthetic contracts cannot qualify GPU capabilities')
        if value['status']=='qualified' and any(body['context'].get(k) is None for k in CONTEXT_KEYS):
            raise ValueError('Qualified capability needs the full device/runtime/tool/mode context')
        for ref in value['evidence']:
            evidence(settings,ref);refs.append(ref)
    return Records(settings).add('capability',name,body,refs)


def resolve(settings,requested):
    store=Records(settings);results=[]
    for entry in store.list('capability'):
        record=store.get('capability',entry['id']);body=record['body']
        mismatches=[k for k in CONTEXT_KEYS if requested.get(k) is None or body['context'].get(k) is None or requested[k]!=body['context'][k]]
        features={k:dict(v,status='not_tested',reason='Context mismatch/unknown: '+','.join(mismatches)) if mismatches else v for k,v in body['features'].items()}
        results.append({'id':record['id'],'record_sha256':record['record_sha256'],'basis':body['basis'],'context_mismatches':mismatches,'features':features})
    return {'schema_version':1,'requested_context':requested,'records':results,
            'default_for_unlisted_features':'not_tested','qualification_is_scoped':True}


def _rows(settings,run,provider,artifacts,view='kernels'):
    result=[];query_ids=[]
    while True:
        q=execute(settings,run,view,provider,limit=1000,offset=len(result),cache=False,artifact_ids=artifacts)
        result.extend(q['rows']);query_ids.append(q['query_id'])
        if len(result)>100000:raise ValueError('Capture audit record budget exceeded; select a bounded official window')
        if not q['page']['has_more']:return result,query_ids


def audit(settings,run,contract,pftrace_id):
    registered=Registry(settings).inspect(run)
    raw=[a for a in registered['artifacts'] if a['format']=='rocpd']
    if not raw:raise ValueError('Capture audit needs registered raw rocpd inputs')
    checks={};errors=[];limits=[]
    def check(name,status,reason):checks[name]={'status':status,'reason':reason}
    check('sealed_inputs','pass','Registered file SHA and absent active WAL/journal verified')
    for artifact in raw:
        try:
            with sqlite_readonly(local_path(artifact['uri'])) as c:
                if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                    check('sqlite_integrity','fail','SQLite quick_check failed');errors.append(artifact['artifact_id'])
        except sqlite3.Error as exc:
            return {'schema_version':1,'run_id':run,'status':'failed','checks':dict(checks,sqlite_integrity={'status':'fail','reason':str(exc)}),
                    'limits':['Malformed/truncated DB is not a complete capture'],'queries':[]}
    if 'sqlite_integrity' not in checks:check('sqlite_integrity','pass','All registered raw SQLite inputs pass quick_check')
    try:
        kernels,queries=_rows(settings,run,'rocpd',[a['artifact_id'] for a in raw])
        if not kernels:raise ValueError('No native kernel dispatch records')
        check('native_intervals','pass','All observed raw kernel intervals have integer, nonnegative duration')
    except (ValueError,OSError) as exc:
        return {'schema_version':1,'run_id':run,'status':'failed','checks':dict(checks,native_intervals={'status':'fail','reason':str(exc)}),'limits':['No complete capture qualification'],'queries':[]}
    ranks=Counter(row['rank'] for row in kernels)
    expected=contract.get('expected_ranks')
    mapped=set(r for r in ranks if r is not None)
    check('declared_rank_coverage','unknown' if expected is None else 'pass' if None not in ranks and mapped==set(expected) else 'fail',
          'Observed PID mapping compared with explicit expected ranks; mapping provenance still separate')
    graph_checks=[]
    windows=contract.get('graph_windows',[])
    for window in windows:
        inside=[e for e in kernels if e['rank']==window['rank'] and int(e['start_ns'])>=window['begin_ns'] and int(e['start_ns'])+int(e['duration_ns'])<=window['end_ns']]
        graph_checks.append({'window':window,'observed_kernels':len(inside),'passed':len(inside)==window['expected_kernels']})
    check('declared_graph_windows','pass' if windows and all(w['passed'] for w in graph_checks) else 'fail' if windows else 'unknown',
          'Exact explicitly declared window budgets only; no full-model replay inference')
    for field,key in [('writer_completed','writer_completed'),('loss_count','record_loss')]:
        ref=contract.get(field)
        if ref:
            evidence(settings,ref)
            wanted=True if field=='writer_completed' else 0
            check(key,'pass' if type(ref.get('expected')) is type(wanted) and ref['expected']==wanted else 'fail','Explicit producer evidence assertion verified')
        else:check(key,'unknown','No independent producer completion/loss assertion supplied')
    if pftrace_id:
        exported,pf_queries=_rows(settings,run,'pftrace',[pftrace_id]);queries+=pf_queries
        keys=('name','start_ns','duration_ns','process_id','graph','graph_node','queue','stream')
        signature=lambda rows:Counter(tuple(e.get(k) for k in keys) for e in rows)
        equal=signature(kernels)==signature(exported)
        check('kernel_export_conservation','pass' if equal else 'fail','Every kernel name/time/PID/Graph/node/queue/stream compared; no custom timestamp shifts')
    else:check('kernel_export_conservation','unknown','No selected official PFTrace representation')
    check('cross_rank_clock','unknown','Host/shared namespace and official export are not clock calibration')
    check('normal_performance','unknown','No trace-off A/A or perturbation acceptance inferred from an offline audit')
    check('full_model_coverage','unknown','Declared ROI/window counts do not qualify every request/token')
    Registry.verify(registered['artifacts'])
    failed=any(c['status']=='fail' for c in checks.values())
    limits.extend(['Correlation values stay provider-scoped; not compared across DB/PFTrace',
                   'Zero memory_copy records do not prove absence of transfer',
                   'R1 PID/rank declarations are inferred, not independently verified device ownership'])
    return {'schema_version':1,'run_id':run,'status':'failed' if failed else 'conditional',
            'checks':checks,'rank_counts':{str(k):v for k,v in ranks.items()},'kernel_count':len(kernels),
            'kernel_duration_sum_ns':str(sum(int(e['duration_ns']) for e in kernels)),
            'graph_windows':graph_checks,'queries':queries,'limits':limits,'errors':errors}

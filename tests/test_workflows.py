import copy
import json
from pathlib import Path

import pytest

from rdnascope.core import Settings, file_hash, minimal_identity
from rdnascope.records import Records,evidence
from rdnascope import benchmark,capabilities,analysis,experiments,workloads
from rdnascope.storage import Registry
from rdnascope.query import execute
from rdnascope.lifecycle import CacheStore


@pytest.fixture
def settings(tmp_path):
    s=Settings(data_dir=tmp_path/'state');s.source_roots['test']=tmp_path
    return s


def ref(settings,path,pointer=None,expected=None):
    result={'source_id':'test','relative_path':str(path.relative_to(settings.source_roots['test'])),'sha256':file_hash(path)}
    if pointer is not None:result.update(json_pointer=pointer,expected=expected)
    return result


def proof(settings):
    p=settings.source_roots['test']/'proof.json';p.write_text('{"passed":true,"failed":false}')
    return ref(settings,p,'/passed',True)


def contract():
    return {'schema_version':1,'basis':'synthetic','kind':'cpu_fixture',
        'metric':{'name':'fixture_duration_ns','unit':'ns','direction':'lower'},
        'match_keys':list(benchmark.MATCH_KEYS['cpu_fixture']), 'intentional_changes':['source_digest'],
        'protocol':{'cases':['small'],'boots':3,'warmups':1,'repeats':2,'max_aa_spread':.05,'min_gain':.1,
                    'classification':'formal','sequence':['A','B','B','A','A','B']}}


def context(arm='A'):
    return {'workload_revision':'fixture','runtime_digest':'locked-runtime','source_digest':'source-'+arm,
            'device_set':['cpu'],'profiled':False,'cache_condition':'warm'}


def measurement(settings,cid,name,arm,value,ctx=None,extra=None):
    p=settings.source_roots['test']/(name+'.json')
    body={'schema_version':1,'boot':name,'metric':contract()['metric'],'samples':[
        {'case':'small','repeat':i,'warmup':i==0,'ok':True,'value':value,'actual_output':14,'expected_output':14} for i in range(3)]}
    if extra:extra(body)
    p.write_text(json.dumps(body))
    return benchmark.ingest(settings,name,cid,'metric-json',ref(settings,p),name,arm,ctx or context(arm),resource_ref=proof(settings))


def cohorts(settings,values=(100,100,100,100,100,100)):
    benchmark.register_contract(settings,'protocol',contract())
    a=[];b=[]
    for i,(arm,value) in enumerate(zip(contract()['protocol']['sequence'],values)):
        name=f'{i:03d}-{arm}';measurement(settings,'protocol',name,arm,value)
        (a if arm=='A' else b).append(name)
    return a,b


def test_portable_evidence_typed_assertions_hash_and_traversal(settings,tmp_path):
    good=proof(settings);assert evidence(settings,good)['status']=='verified'
    with pytest.raises(ValueError,match='assertion failed'):evidence(settings,dict(good,expected=1))
    with pytest.raises(ValueError,match='traversal'):evidence(settings,dict(good,relative_path='../proof.json'))
    (tmp_path/'proof.json').write_text('{}')
    with pytest.raises(ValueError,match='SHA mismatch'):evidence(settings,good)


def test_capabilities_scoped_to_exact_context_and_no_cpu_upgrade(settings):
    ctx={k:'value' for k in capabilities.CONTEXT_KEYS};ctx.update(world=2,gfx='gfx1201')
    body={'schema_version':1,'basis':'historical_reanalysis','context':ctx,'features':{
        'kernel_dispatch':{'status':'conditional','scope':'two ROI replays only','reason':'observed','evidence':[proof(settings)]}},'revalidate_on':['tool build change']}
    capabilities.register(settings,'gpu-roi',body)
    assert capabilities.resolve(settings,ctx)['records'][0]['features']['kernel_dispatch']['status']=='conditional'
    assert capabilities.resolve(settings,dict(ctx,gfx='another-gfx'))['records'][0]['features']['kernel_dispatch']['status']=='not_tested'
    bad=copy.deepcopy(body);bad['basis']='synthetic';bad['features']['kernel_dispatch']['status']='qualified'
    with pytest.raises(ValueError,match='cannot qualify'):capabilities.register(settings,'false-upgrade',bad)


def test_aa_uses_boots_keeps_drift_and_does_not_pretend_tokens_independent(settings):
    benchmark.register_contract(settings,'protocol',contract())
    ids=[]
    for i,v in enumerate([100,160,100]):
        name='boot-'+str(i);measurement(settings,'protocol',name,'A',v);ids.append(name)
    result=benchmark.aa(settings,ids)
    assert result['status']=='inconclusive' and result['gates'][0]['relative_range']==.6
    assert result['unit']=='independent_boot_median'


def test_formal_compare_allows_only_preregistered_source_change(settings):
    a,b=cohorts(settings,[100,80,80,100,100,80])
    result=benchmark.compare(settings,a,b)
    assert result['passed'] and result['classification']=='formal' and not result['adopted']
    assert result['intentional_changes']==[{'key':'source_digest','baseline':'source-A','candidate':'source-B'}]
    assert result['gates'][0]['relative_gain']==pytest.approx(.2)


def test_unmatched_context_and_reused_boot_input_downgrade(settings):
    benchmark.register_contract(settings,'protocol',contract());ids=[]
    for i in range(3):
        name='bad-'+str(i);ctx=context();ctx['cache_condition']=None if i==1 else 'warm'
        measurement(settings,'protocol',name,'A',100,ctx);ids.append(name)
    result=benchmark.aa(settings,ids);assert 'unknown_condition:cache_condition' in result['issues']
    original=Records(settings).get('measurement',ids[0]);body=dict(original['body'],boot='another-boot')
    Records(settings).add('measurement','relabel',body,original['evidence'])
    assert any('reused_input' in i for i in benchmark.aa(settings,[ids[0],ids[2],'relabel'])['issues'])


def test_failed_or_missing_samples_and_unverified_output_cannot_pass(settings):
    benchmark.register_contract(settings,'protocol',contract());ids=[]
    for i in range(3):
        name='fail-'+str(i)
        measurement(settings,'protocol',name,'A',100,extra=lambda b:b['samples'][1].update(actual_output=None,expected_output=None))
        ids.append(name)
    result=benchmark.aa(settings,ids)
    assert not result['passed'] and any('output_unqualified' in i for i in result['issues'])


def test_reference_unknown_shape_never_generates_reachable_efficiency(settings):
    keys=list(set(benchmark.MATCH_KEYS['kernel'])-{'profiled'})
    body={'schema_version':1,'basis':'historical_reanalysis','kind':'kernel','reference_type':'reachable_calibration',
        'context':{k:'declared' for k in keys},'match_keys':keys,'metric':'duration_ns','unit':'ns','value':10,
        'uncertainty':None,'qualification':'unknown','capability_id':None,'revalidate_on':['shape/runtime'],'measurement_ids':[]}
    body['context']['shape']=None
    benchmark.register_reference(settings,'unknown-shape',body)
    result=benchmark.reference_match(settings,'unknown-shape',body['context'])
    assert not result['applicable'] and result['value'] is None and 'shape' in result['unknown_conditions']
    body['qualification']='qualified'
    with pytest.raises(ValueError,match='complete context'):benchmark.register_reference(settings,'false-ref',body,[proof(settings)])


def test_thread_config_does_not_require_kernel_layout_fixture_but_still_gates_model(settings):
    a,b=cohorts(settings,[100,80,80,100,100,80])
    spec={'basis':'synthetic','candidate_type':'thread_config','hypothesis':'One isolated thread configuration',
          'baseline':{'source_digest':'source-A'},'candidate':{'source_digest':'source-B'},
          'gate_evidence':{k:proof(settings) for k in experiments.GATES['thread_config']},
          'aa_measurements':a,'baseline_measurements':a,'candidate_measurements':b}
    result=experiments.evaluate(settings,'config-candidate',spec)['body']
    assert result['decision']=='validated' and not result['adopted']
    assert 'shape_layout_coverage' not in result['stages']['gates']
    wrong=dict(spec,baseline={'source_digest':'unrelated'})
    assert experiments.evaluate(settings,'wrong-source',wrong)['body']['decision']=='inconclusive'


def test_kernel_control_failure_not_misreported_as_candidate_math_rejection(settings):
    true=proof(settings);false=dict(true,json_pointer='/failed',expected=False)
    spec={'basis':'synthetic','candidate_type':'kernel_layout','hypothesis':'isolated layout',
          'baseline':{},'candidate':{},'gate_evidence':{k:true for k in experiments.GATES['kernel_layout']}}
    spec['gate_evidence']['independent_baseline']=false
    body=experiments.evaluate(settings,'invalid-control',spec)['body']
    assert body['decision']=='inconclusive' and 'control_invalid' in body['stages']['reason']
    assert body['stages']['model_comparison']['status']=='not_run'
    spec['gate_evidence']['independent_baseline']=true
    spec['gate_evidence']['local_stability']=false;spec['gate_evidence']['local_effect']=false
    body=experiments.evaluate(settings,'unstable-local',spec)['body']
    assert body['decision']=='inconclusive' and body['stages']['reason']=='local_performance_not_identifiable'


def register_trace(settings,tmp_path):
    path=tmp_path/'chrome.json';path.write_text(json.dumps({'traceEvents':[
        {'ph':'X','name':'copyBuffer','cat':'kernel','pid':1,'ts':1,'dur':2},
        {'ph':'X','name':'ncclAllReduce','cat':'kernel','pid':2,'ts':5,'dur':3}]}))
    identity=minimal_identity('trace');identity['role']='fixture';identity['workload']['tp']=2
    Registry(settings).register(identity,[{'path':str(path)}])
    return path


def test_three_diagnostic_domains_preserve_unknowns_and_verify_source(settings,tmp_path):
    source=register_trace(settings,tmp_path)
    report=analysis.analyze(settings,'trace','triage')
    assert {f['domain'] for f in report['findings']}=={'model','kernel','multigpu'}
    assert all(f['numeric_gap'] is None and f['recoverable_wall_ns'] is None for f in report['findings'])
    assert not report['findings'][-1]['position']['qualified_collective_entry_skews']
    assert Records(settings).verify_tree('case','triage')['status']=='verified'
    source.write_text('{}')
    with pytest.raises(ValueError,match='Evidence changed'):Records(settings).verify_tree('case','triage')


def test_semantic_exact_proof_and_dependency_cycle_rejected(settings,tmp_path):
    register_trace(settings,tmp_path);q=execute(settings,'trace','events')
    entries=[{'event_id':r['event_id'],'association':'exact','phase':'decode','proof':proof(settings)} for r in q['rows']]
    body={'schema_version':1,'basis':'synthetic','run_id':'trace','provider':q['provenance']['provider'],
          'input_artifacts':q['provenance']['inputs'],'entries':entries,'dependencies':[],
          'clock':{'calibrated':False},'scope_complete':False}
    analysis.register_map(settings,'scoped-map',body)
    assert analysis.analyze(settings,'trace','mapped',semantic_map='scoped-map')['findings'][0]['position']['exact_groups']
    body['dependencies']=[{'source':entries[0]['event_id'],'target':entries[0]['event_id'],'association':'exact','proof':proof(settings)}]
    with pytest.raises(ValueError,match='cycle'):analysis.register_map(settings,'bad-map',body)


def test_gpu_resource_refusal_never_spawns_adapter(settings,monkeypatch):
    settings.adapters['gpu']={'gpu':True,'executable':'/not-launched'}
    monkeypatch.setattr('rdnascope.resources.discover',lambda *a,**k:{'status':'resource_blocked','foreign_processes':[{'pid':123}]})
    monkeypatch.setattr('rdnascope.workers.start',lambda *a,**k:pytest.fail('occupied GPU must never launch'))
    result=workloads.external(settings,{'run_id':'blocked','adapter':'gpu','physical_gpus':[0,2]})
    assert result['status']=='resource_blocked' and not result['child_started']


def test_device_snapshot_refuses_low_or_unobservable_ram(settings,tmp_path,monkeypatch):
    from rdnascope.resources import discover
    nodes=tmp_path/'nodes';node=nodes/'0';node.mkdir(parents=True)
    (node/'gpu_id').write_text('42');(node/'properties').write_text('location_id 768\ndomain 0\n')
    procs=tmp_path/'kfd-proc';procs.mkdir();proc=tmp_path/'proc';proc.mkdir()
    smi=tmp_path/'smi';smi.write_text('bound tool fixture')
    monkeypatch.setattr('rdnascope.resources.bounded_process',lambda *a,**kw:(json.dumps({'card0':{
        'PCI Bus':'0000:03:00.0','Unique ID':'0x1234','Card Series':'fixture','GFX Version':'gfx1201'}}),''))
    settings.machine={'smi_executable':str(smi),'kfd_topology':str(nodes),'kfd_processes':str(procs),'proc_root':str(proc),
                      'min_available_ram_bytes':2048}
    (proc/'meminfo').write_text('MemAvailable: 1 kB\n')
    low=discover(settings,[0]);assert low['status']=='resource_blocked' and low['available_ram_bytes']==1024
    assert 'host_ram_below_profile_admission_threshold' in low['errors']
    (proc/'meminfo').unlink()
    assert 'host_ram_observation_unavailable' in discover(settings,[0])['errors']
    (proc/'meminfo').write_text('MemAvailable: 4 kB\n')
    assert discover(settings,[0])['status']=='available_snapshot_only'


def test_reserved_evidence_binding_cannot_silently_point_elsewhere(tmp_path):
    profile=tmp_path/'machine.toml';profile.write_text('[sources]\nrdnascope-evidence="other"\n')
    with pytest.raises(ValueError,match='reserved'):Settings(profile,data_dir=tmp_path/'state')


def test_second_workload_runs_without_model_and_pins_measurement_evidence(settings):
    body=contract();body['protocol']['cases']=['small','large'];body['match_keys'].append('variant');body['intentional_changes']=['variant']
    benchmark.register_contract(settings,'cpu-demo',body)
    report=workloads.fixture(settings,'cpu-demo','cpu-independent',phase='aa')
    assert report['status']=='completed' and len(report['measurements'])==3
    assert report['report']['status'] in ('passed','inconclusive')
    assert all(Records(settings).get('measurement',n)['body']['output_audit']=='verified' for n in report['measurements'])
    inventory=CacheStore(settings).inventory()
    assert len([i for i in inventory['items'] if i['kind']=='job' and i['references']])==3


def test_closed_semantic_dependency_scope_reports_lower_bound_not_saved_wall(settings,tmp_path):
    register_trace(settings,tmp_path);q=execute(settings,'trace','events')
    entries=[{'event_id':r['event_id'],'association':'exact','phase':'decode','proof':proof(settings)} for r in q['rows']]
    body={'schema_version':1,'basis':'synthetic','run_id':'trace','provider':q['provenance']['provider'],
          'input_artifacts':q['provenance']['inputs'],'entries':entries,
          'dependencies':[{'source':entries[0]['event_id'],'target':entries[1]['event_id'],'association':'exact','proof':proof(settings)}],
          'clock':{'calibrated':False,'scope_proof':proof(settings)},'scope_complete':True}
    analysis.register_map(settings,'closed',body)
    report=analysis.analyze(settings,'trace','closed-report',semantic_map='closed')
    projection=report['findings'][0]['position']['dependency_projection']
    assert projection['lower_bound_ns']=='5000' and projection['residual_ns']=='2000'
    assert report['findings'][0]['recoverable_wall_ns'] is None


def test_owned_evidence_output_is_bounded_and_can_be_registered_readonly(settings):
    import sys
    from rdnascope import workers
    spec={'kind':'capture-fixture','argv':[sys.executable,'-c','import os,json;from pathlib import Path;(Path(os.environ["RDNASCOPE_JOB_OUTPUT"])/"trace.json").write_text(json.dumps({"traceEvents":[]}))'],
          'reserve_bytes':2*1024*1024,'log_bytes':1024*1024,'timeout_seconds':5,'max_rss_bytes':None,'evidence_run':'fresh-capture'}
    started=workers.start(settings,spec);job=workers.wait(settings,started['job'],15)
    assert job['status']=='passed' and job['result']['evidence_output']['gc_policy']=='external_evidence_never_deleted'
    path=Path(job['result']['evidence_output']['path'])/'trace.json'
    Registry(settings).register(minimal_identity('captured'),[{'path':str(path)}])
    assert Registry(settings).inspect('captured')['registered_bytes_verified']
    with pytest.raises(ValueError,match='fresh owned'):workers.start(settings,spec)


def test_adapter_freezes_helpers_before_execution(settings,tmp_path):
    import sys
    script=tmp_path/'helper.py';script.write_text('from pathlib import Path\nprint(Path(__file__).parent.name)\n')
    settings.adapters['cpu']={'gpu':False,'executable':sys.executable,'executable_sha256':file_hash(Path(sys.executable)),
        'identity_files':[{'path':str(script),'sha256':file_hash(script)}],'actions':{'run':[str(script)]}}
    result=workloads.external(settings,{'run_id':'frozen-helper','adapter':'cpu','action':'run','timeout_seconds':5,'reserve_bytes':2*1024*1024})
    assert result['status']=='passed'
    job_dir=Path(result['job']['logs'])
    assert (job_dir/'stdout.log').read_text().strip()=='bound-inputs'
    assert (job_dir/'bound-inputs/manifest.json').exists()


def test_truncated_native_database_never_qualifies(settings,tmp_path):
    database=tmp_path/'truncated.db';database.write_bytes(b'SQLite format 3\x00'+b'\x00'*112)
    Registry(settings).register(minimal_identity('truncated'),[{'path':str(database),'format':'rocpd'}])
    result=capabilities.audit(settings,'truncated',{},None)
    assert result['status']=='failed' and result['checks']['sqlite_integrity']['status']=='fail'


def test_http_model_report_uses_http_metrics_and_keeps_itl_unknown(settings,tmp_path):
    path=tmp_path/'http.json';path.write_text(json.dumps([{'case':'tiny','repeat':0,'warmup':False,'wall_seconds':2,'first_text_seconds':.3,'timings':{'predicted_per_second':4}}]))
    Registry(settings).register(minimal_identity('http-run'),[{'path':str(path),'format':'http'}])
    report=analysis.analyze(settings,'http-run','http-model')
    assert report['findings'][0]['position']['case_metrics']['tiny']['http_wall_median_seconds']==2
    assert {f['domain'] for f in report['findings']}=={'model','kernel','multigpu'}
    assert all(f['numeric_gap'] is None for f in report['findings'])


def test_screening_two_per_arm_requires_separate_baseline_aa(settings):
    body=contract();body['protocol']['classification']='screening';body['protocol']['sequence']=['A','B','B','A']
    benchmark.register_contract(settings,'screen',body);a=[];b=[]
    for i,arm in enumerate(body['protocol']['sequence']):
        name=f'screen-{i:03d}';measurement(settings,'screen',name,arm,100 if arm=='A' else 80);(a if arm=='A' else b).append(name)
    result=benchmark.compare(settings,a,b)
    assert result['passed'] and result['classification']=='screening' and not result['adopted']
    assert not benchmark.aa(settings,a)['passed']


def test_clock_flag_alone_cannot_qualify_cross_rank_skew(settings,tmp_path):
    register_trace(settings,tmp_path);q=execute(settings,'trace','events')
    body={'schema_version':1,'basis':'synthetic','run_id':'trace','provider':q['provenance']['provider'],
        'input_artifacts':q['provenance']['inputs'],'entries':[],'dependencies':[],
        'clock':{'calibrated':True,'uncertainty_ns':1,'proof':proof(settings)},'scope_complete':False}
    with pytest.raises(ValueError,match='scoped capability'):analysis.register_map(settings,'fake-clock',body)


def test_model_gap_requires_matching_verified_measurements_and_reference(settings,tmp_path):
    c=contract();c.update(basis='live',kind='model',match_keys=list(benchmark.MATCH_KEYS['model']))
    c['metric']={'name':'http_wall_seconds','unit':'s','direction':'lower'}
    c['protocol'].update(cases=['tiny'],warmups=0,repeats=1)
    benchmark.register_contract(settings,'model-protocol',c)
    ctx={k:'fixed' for k in c['match_keys']};ctx.update(profiled=False,tp=1,ep=1,graph=False,concurrency=1,output_tokens=1,device_set=['fixture-device'])
    oracle=tmp_path/'oracle.json';oracle.write_text(json.dumps([{'case':'tiny','text_sha256':'0'*64,'usage':{'completion_tokens':1}}]))
    groups={};files={}
    for arm,value in [('baseline',1.0),('target',1.5)]:
        groups[arm]=[];files[arm]=[]
        for i in range(3):
            name=f'{arm}-{i}';path=tmp_path/(name+'.json')
            path.write_text(json.dumps([{'case':'tiny','repeat':0,'warmup':False,'wall_seconds':value,'text_sha256':'0'*64,
                'usage':{'completion_tokens':1},'boot_tag':name}]))
            benchmark.ingest(settings,name,'model-protocol','freetoken-http',ref(settings,path),name,'A',ctx,ref(settings,oracle),proof(settings))
            groups[arm].append(name);files[arm].append(path)
    reference={'schema_version':1,'basis':'live','kind':'model','reference_type':'same_condition_baseline',
        'context':dict(ctx,case='tiny'),'match_keys':c['match_keys']+['case'],'metric':'http_wall_seconds','unit':'s','value':1.0,
        'uncertainty':0,'qualification':'qualified','capability_id':None,'revalidate_on':['conditions change'],'measurement_ids':groups['baseline']}
    benchmark.register_reference(settings,'healthy',reference,[proof(settings)])
    identity=minimal_identity('model-target');identity['extensions']['observation_basis']='live'
    Registry(settings).register(identity,[{'path':str(path),'format':'http'} for path in files['target']])
    report=analysis.analyze(settings,'model-target','model-gap',references=['healthy'],measurement_ids=groups['target'])
    gaps=[f for f in report['findings'] if f['numeric_gap'] is not None]
    assert len(gaps)==1 and gaps[0]['numeric_gap']==.5 and gaps[0]['reference']['unit']=='s'
    assert gaps[0]['recoverable_wall_ns'] is None
    assert Records(settings).verify_tree('case','model-gap')['status']=='verified'

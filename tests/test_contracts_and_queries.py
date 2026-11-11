import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from rdnascope.core import Settings, canonical, file_hash, minimal_identity, schema, validate
from rdnascope.query import execute
from rdnascope.storage import Registry


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / 'managed')


def chrome(path, start=2):
    path.write_text(json.dumps({'displayTimeUnit':'ns','traceEvents':[
        {'ph':'X','name':'vector_add','cat':'kernel','pid':7,'tid':2,'ts':start,'dur':3,
         'args':{'phase':'decode','position':8}},
        {'ph':'X','name':'hipGraphLaunch','cat':'hip_api','pid':7,'tid':1,'ts':1,'dur':1}]}))
    return path


def register(settings, path, name='sample', identity=None, fmt='auto'):
    return Registry(settings).register(identity or minimal_identity(name),[{'path':str(path),'format':fmt}])


def rocpd(path, suffix='abc', duration=30):
    c=sqlite3.connect(path)
    c.executescript(f'''
    CREATE TABLE rocpd_info_process_{suffix}(id INTEGER PRIMARY KEY,pid INTEGER);
    CREATE TABLE rocpd_info_kernel_symbol_{suffix}(id INTEGER PRIMARY KEY,display_name TEXT,kernel_name TEXT);
    CREATE TABLE rocpd_kernel_dispatch_{suffix}(id INTEGER PRIMARY KEY,pid INTEGER,kernel_id INTEGER,start INTEGER,end INTEGER,queue_id INTEGER,stream_id INTEGER,graph_exec_id INTEGER,graph_node_id INTEGER,agent_id INTEGER);
    INSERT INTO rocpd_info_process_{suffix} VALUES(1,7);
    INSERT INTO rocpd_info_kernel_symbol_{suffix} VALUES(1,'vector_add','vector_add');
    INSERT INTO rocpd_kernel_dispatch_{suffix} VALUES(1,1,1,100,{100+duration},2,4,1,1,9);
    INSERT INTO rocpd_kernel_dispatch_{suffix} VALUES(2,1,1,200,{200+duration},2,4,1,2,9);
    ''')
    c.commit();c.close()
    return path


def test_contracts_reject_unknown_version_field_and_duplicate_mapping():
    identity=minimal_identity('test')
    for change in [{'schema_version':2},{'unregistered_field':True}]:
        with pytest.raises(ValueError):validate('identity',dict(identity,**change))
    r={'rank':0,'process_id':7,'device_uuid':None,'pci':None,'gfx':None}
    with pytest.raises(ValueError):validate('identity',dict(identity,ranks=[r,r]))
    assert schema('identity')['$schema'].endswith('2020-12/schema')


def test_artifact_content_identity_and_nested_quality_are_validated(settings,tmp_path):
    p=chrome(tmp_path/'evidence.json')
    registered=register(settings,p)
    artifact=dict(registered['artifacts'][0],artifact_id='sha256:'+'0'*64)
    with pytest.raises(ValueError,match='match its content SHA'):validate('artifact',artifact)
    q=execute(settings,'sample')
    q['quality']['schema_version']=99
    with pytest.raises(ValueError,match='quality schema'):validate('query-result',q)
    q=execute(settings,'sample');q['page']['returned']+=1
    with pytest.raises(ValueError,match='page count'):validate('query-result',q)


def test_numeric_overflow_and_malformed_event_are_structured_failures(settings,tmp_path):
    from rdnascope.core import read_json
    from rdnascope.cli import main
    huge=tmp_path/'overflow.json';huge.write_text('[1e999]')
    with pytest.raises(ValueError,match='Non-finite'):read_json(huge)
    source=tmp_path/'invalid.json';source.write_text('{"traceEvents":[null]}')
    register(settings,source)
    assert main(['--data-dir',str(settings.data_dir),'query','sample'])==2
    http=tmp_path/'http.json';http.write_text('[{"wall_seconds":1e308}]')
    register(settings,http,name='overflow')
    with pytest.raises(ValueError,match='finite numeric range'):execute(settings,'overflow')


def test_subprocess_budget_and_timeout_reap_only_own_child():
    from rdnascope.providers import bounded_process
    with pytest.raises(ValueError,match='output budget'):
        bounded_process([sys.executable,'-c','print("x"*4096)'],1,max_output=128)
    with pytest.raises(TimeoutError,match='time budget'):
        bounded_process([sys.executable,'-c','import time; time.sleep(10)'],.03)
    out,err=bounded_process([sys.executable,'-c','print("usable")'],1)
    assert out.strip()=='usable' and not err


def test_config_relative_paths_are_config_relative_and_doctor_does_not_write(tmp_path,monkeypatch):
    folder=tmp_path/'profiles';folder.mkdir();p=folder/'machine.toml'
    p.write_text('[paths]\ndata_dir="../state"\ncache_dir="../cache"\n[tools]\ntrace_processor="../bin/tp"\n')
    monkeypatch.chdir(tmp_path)
    s=Settings(p)
    assert s.data_dir==tmp_path/'state' and s.trace_processor==str(tmp_path/'bin/tp')
    r=subprocess.run([sys.executable,'-m','rdnascope','--config',str(p),'doctor'],capture_output=True,text=True)
    assert r.returncode==0 and json.loads(r.stdout)['scope']=='offline_only_no_gpu_probe'
    assert not s.data_dir.exists() and not s.cache_dir.exists()


def test_read_only_reference_shared_cache_and_cross_run_reuse(settings,tmp_path):
    source=chrome(tmp_path/'source with spaces.json');before=file_hash(source)
    register(settings,source)
    first=execute(settings,'sample');second=execute(settings,'sample')
    register(settings,source,'second')
    third=execute(settings,'second')
    assert not first['cache_hit'] and second['cache_hit'] and third['cache_hit']
    assert first['query_id']==third['query_id'] and third['run_id']=='second'
    stats=Registry(settings).stats()
    assert stats['derived_query_cache_files']==1 and stats['source_bytes_copied']==0
    assert stats['external_unique_content_bytes']==source.stat().st_size
    assert file_hash(source)==before
    with pytest.raises(FileExistsError):register(settings,source)


def test_source_mutation_refuses_cache_hit(settings,tmp_path):
    p=chrome(tmp_path/'source.json');register(settings,p);execute(settings,'sample')
    p.write_text('{}')
    with pytest.raises(ValueError,match='Evidence changed'):execute(settings,'sample')


def test_mid_query_source_mutation_refused_before_cache_commit(settings,tmp_path,monkeypatch):
    from rdnascope import providers
    p=chrome(tmp_path/'source.json');register(settings,p)
    original=providers.json_query
    def changing(*args,**kwargs):
        r=original(*args,**kwargs);p.write_text('{}');return r
    monkeypatch.setattr(providers,'json_query',changing)
    with pytest.raises(ValueError,match='Evidence changed'):execute(settings,'sample')
    assert not list((settings.cache_dir/'queries').glob('*.json'))


def test_corrupt_cache_is_not_silently_accepted(settings,tmp_path):
    p=chrome(tmp_path/'source.json');register(settings,p);r=execute(settings,'sample')
    cache=settings.cache_dir/'queries'/(r['query_id']+'.json');v=json.loads(cache.read_text())
    v['payload']['rows'][0]['count']=999;cache.write_text(json.dumps(v))
    with pytest.raises(ValueError,match='cache object failed'):execute(settings,'sample')


def test_nanosecond_integer_precision_display_unit_and_unknown_clock(settings,tmp_path):
    p=chrome(tmp_path/'source.json',2**53+1)
    identity=minimal_identity('sample');identity['semantics']['time_unit']='ns'
    identity['clock']['calibration']='declared';identity['clock']['uncertainty_ns']=1
    identity['workload'].update(tp=2,graph=True)
    identity['ranks']=[{'rank':0,'process_id':7,'device_uuid':None,'pci':None,'gfx':None}]
    register(settings,p,identity=identity)
    r=execute(settings,'sample','kernels')
    assert r['rows'][0]['start_ns']==str(2**53+1) and r['rows'][0]['duration_ns']=='3'
    assert r['rows'][0]['phase']=='decode' and r['rows'][0]['association']=='inferred'
    caps=r['quality']['capabilities']
    assert caps['cross_rank_clock']['status']=='unknown' and caps['normal_performance']['status']=='unknown'
    assert caps['declared_rank_metadata']['status']=='fail'


def test_chrome_us_default_is_not_display_time_unit(settings,tmp_path):
    register(settings,chrome(tmp_path/'source.json'))
    r=execute(settings,'sample','kernels');assert r['rows'][0]['start_ns']=='2000'


def test_rocpd_multiple_sources_native_locations_and_page(settings,tmp_path):
    a=rocpd(tmp_path/'a.db');b=rocpd(tmp_path/'b.db',suffix='def')
    before=[file_hash(p) for p in (a,b)]
    Registry(settings).register(minimal_identity('sample'),[{'path':str(p)} for p in (a,b)])
    rows=[]
    for offset in range(4):
        r=execute(settings,'sample','kernels',limit=1,offset=offset);rows.extend(r['rows'])
        assert r['page']['has_more']==(offset<3)
    assert len({r['event_id'] for r in rows})==4
    assert all(r['duration_ns']=='30' and r['graph']==1 and r['rank'] is None for r in rows)
    summary=execute(settings,'sample')['rows'];assert sum(x['count'] for x in summary)==4
    assert [file_hash(p) for p in (a,b)]==before
    for p in (a,b):
        assert not Path(str(p)+'-wal').exists() and not Path(str(p)+'-shm').exists()


def test_negative_rocpd_interval_and_unsealed_db_rejected(settings,tmp_path):
    p=rocpd(tmp_path/'bad.db',duration=-1);register(settings,p)
    with pytest.raises(ValueError,match='negative timestamp'):execute(settings,'sample')
    other=rocpd(tmp_path/'unsealed.db');Path(str(other)+'-wal').write_bytes(b'active')
    with pytest.raises(ValueError,match='Unsealed SQLite'):register(settings,other,'other')


def test_lineage_missing_parent_and_cycle_do_not_create_partial_runs(settings,tmp_path):
    a=chrome(tmp_path/'a.json');b=chrome(tmp_path/'b.json',start=5)
    entries=[{'path':str(a),'label':'a','derived_from':['b']},{'path':str(b),'label':'b','derived_from':['a']}]
    with pytest.raises(ValueError,match='Cyclic'):Registry(settings).register(minimal_identity('sample'),entries)
    assert not Registry(settings).path.exists()
    entries[0]['derived_from']=[]
    r=Registry(settings).register(minimal_identity('sample'),entries)
    assert r['derivations'][0]['status']=='declared_not_semantically_audited'


def test_http_metrics_are_not_token_itl_or_independent_parity(settings,tmp_path):
    p=tmp_path/'performance.json';p.write_text(json.dumps([{'case':'tiny','wall_seconds':2,'first_text_seconds':.4,
        'warmup':False,'usage':{'completion_tokens':4},'timings':{'predicted_per_second':3},'output_matches_frozen_oracle':True}]))
    register(settings,p)
    r=execute(settings,'sample','metrics');e=r['rows'][0]
    assert e['http_wall_seconds']==2 and e['http_first_text_seconds']==.4
    assert 'itl' not in e and 'ttft' not in e
    assert r['quality']['capabilities']['output_correctness']['status']=='unknown'
    unsupported=execute(settings,'sample','collectives')
    assert unsupported['rows']==[] and unsupported['quality']['capabilities']['query_view']['status']=='unknown'


def test_legacy_macro_not_promoted_to_native_and_no_dispatch_clock_stitch(settings,tmp_path):
    folder=tmp_path/'legacy';(folder/'normalized').mkdir(parents=True)
    e={'name':'model','category':'kernel','rank':0,'start_ns':12,'duration_ns':40,
       'evidence_level':'macro_hip_span','dispatch':3,'clock_domain':'rank0:dispatch3'}
    events=folder/'normalized/events.jsonl';events.write_text(json.dumps(e)+'\n')
    (folder/'manifest.json').write_text(json.dumps({'import_status':'complete','normalized_sha256':file_hash(events)}))
    register(settings,folder)
    r=execute(settings,'sample','events')
    assert r['rows'][0]['category']=='macro_span' and r['rows'][0]['clock_domain']=='rank0:dispatch3'
    assert execute(settings,'sample','kernels')['rows']==[]


def test_input_and_identity_versions_refused_without_rewriting_existing_files(settings,tmp_path):
    p=chrome(tmp_path/'source.json');register(settings,p)
    with sqlite3.connect(Registry(settings).path) as c:
        c.execute("UPDATE runs SET identity_json='{}'")
    with pytest.raises(ValueError):Registry(settings).inspect('sample')


def test_legacy_bridge_preserves_arguments_and_exit_code(tmp_path,monkeypatch):
    from rdnascope.legacy import main
    monkeypatch.delenv('RDNASCOPE_LEGACY_DELEGATING',raising=False)
    exe=tmp_path/'original';exe.write_text('#!/usr/bin/env python3\nimport json,sys,os\nfrom pathlib import Path\nPath(__file__).with_name("forwarded.json").write_text(json.dumps({"args":sys.argv[1:],"cwd":os.getcwd()}))\nsys.exit(17)\n');exe.chmod(0o755)
    p=tmp_path/'profile.toml';p.write_text('[legacy]\nexecutable="original"\n')
    monkeypatch.chdir(tmp_path)
    assert main(['--config',str(p),'import','literal $(not-a-command)','--run','abc'])==17
    report=(tmp_path/'forwarded.json').read_text()
    assert json.loads(report)=={'args':['import','literal $(not-a-command)','--run','abc'],'cwd':str(tmp_path)}
    monkeypatch.setenv('RDNASCOPE_LEGACY_DELEGATING','1')
    assert main(['--config',str(p),'doctor'])==2
    assert (tmp_path/'forwarded.json').read_text()==report


def test_bounded_pages_and_unsupported_future_schema(settings,tmp_path):
    register(settings,chrome(tmp_path/'source.json'))
    for limit,offset in [(0,0),(1001,0),(1,-1)]:
        with pytest.raises(ValueError):execute(settings,'sample',limit=limit,offset=offset)
    with sqlite3.connect(Registry(settings).path) as c:c.execute('PRAGMA user_version=2')
    with pytest.raises(ValueError,match='Unsupported registry'):Registry(settings).inspect('sample')


def test_related_representations_require_explicit_selection(settings,tmp_path):
    a=chrome(tmp_path/'full.json');b=chrome(tmp_path/'window.json',start=5)
    r=Registry(settings).register(minimal_identity('sample'),[{'path':str(a),'label':'full'},
        {'path':str(b),'label':'window','derived_from':['full']}])
    with pytest.raises(ValueError,match='double-count'):execute(settings,'sample')
    one=r['artifacts'][0]['artifact_id']
    assert sum(x['count'] for x in execute(settings,'sample',artifact_ids=[one])['rows'])==2


def test_concurrent_first_registration_commits_two_complete_runs(settings,tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    p=chrome(tmp_path/'source.json')
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(register,settings,p,name) for name in ['first','second']]
        results=[f.result() for f in futures]
    assert len(results)==2 and Registry(settings).stats()['runs']==2


def test_symlink_cache_directory_refused(settings,tmp_path):
    p=chrome(tmp_path/'source.json');register(settings,p)
    outside=tmp_path/'outside';outside.mkdir();settings.cache_dir.mkdir(parents=True)
    (settings.cache_dir/'queries').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='must not be a symlink'):execute(settings,'sample')
    assert not list(outside.iterdir())

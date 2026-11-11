import copy
import json
import os
from pathlib import Path
import sqlite3

import pytest

from rdnascope.core import Settings, file_hash, minimal_identity
from rdnascope.lifecycle import CacheStore, process_identity
from rdnascope.query import execute
from rdnascope.storage import Registry
from rdnascope import namespaces


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path/'state')


def query(settings, tmp_path, name='sample'):
    source=tmp_path/(name+'.json')
    source.write_text(json.dumps({'traceEvents':[{'ph':'X','name':name,'cat':'kernel','ts':1,'dur':2}]}))
    Registry(settings).register(minimal_identity(name),[{'path':str(source)}])
    return 'query:'+execute(settings,name)['query_id']


@pytest.fixture
def fingerprint():
    return json.loads((Path(__file__).parents[1]/'examples/cache-fingerprint.json').read_text())


def test_explicit_gc_protects_refs_leases_external_and_unmanaged(settings,tmp_path):
    store=CacheStore(settings)
    pinned=query(settings,tmp_path,'pinned');active=query(settings,tmp_path,'active');free=query(settings,tmp_path,'free')
    external=tmp_path/'free.json';original=file_hash(external)
    unmanaged=settings.cache_dir/'queries'/('a'*64+'.json');unmanaged.write_text('unmanaged')
    store.reference(pinned,'case:kept')
    with store.lease(active,'reader'):
        plan=store.gc_preview(older_than=0)
        assert [c['id'] for c in plan['candidates']]==[free]
        assert store.path(free).exists()
        result=store.gc_apply(plan)
        assert [c['id'] for c in result['deleted']]==[free]
        assert store.path(active).exists() and store.path(pinned).exists()
    assert unmanaged.read_text()=='unmanaged' and file_hash(external)==original
    item=next(i for i in store.inventory()['items'] if i['id']==free)
    assert item['status']=='deleted' and not item['bytes_available'] and item['sha']
    with pytest.raises(ValueError,match='consumed'):store.gc_apply(plan)
    assert execute(settings,'free')['cache_hit'] is False


def test_gc_rechecks_access_pins_and_leases_after_preview(settings,tmp_path):
    store=CacheStore(settings);item=query(settings,tmp_path)
    plan=store.gc_preview(0)
    execute(settings,'sample')
    assert store.gc_apply(plan)['skipped'][0]['reasons']==['changed_since_preview']
    plan=store.gc_preview(0);store.reference(item,'manual-pin')
    assert 'pinned_or_referenced' in store.gc_apply(plan)['skipped'][0]['reasons']
    store.reference(item,'manual-pin',remove=True);plan=store.gc_preview(0)
    with store.lease(item,'reader'):
        assert 'active_lease' in store.gc_apply(plan)['skipped'][0]['reasons']
    assert store.path(item).exists()


def test_gc_requires_recorded_unchanged_plan_and_explicit_age(settings,tmp_path):
    store=CacheStore(settings);item=query(settings,tmp_path)
    assert store.gc_preview()['candidates']==[]
    plan=store.gc_preview(0);forged=copy.deepcopy(plan);forged['candidates'][0]['bytes']+=1
    with pytest.raises(ValueError,match='unknown, changed'):store.gc_apply(forged)
    assert store.path(item).exists()
    other=CacheStore(Settings(data_dir=tmp_path/'other'))
    with pytest.raises(ValueError,match='another store'):other.gc_apply(plan)


def test_gc_never_follows_replaced_symlinks_or_shared_hardlinks(settings,tmp_path):
    store=CacheStore(settings);item=query(settings,tmp_path)
    plan=store.gc_preview(0);path=store.path(item)
    outside=tmp_path/'outside';outside.write_text('retained')
    path.unlink();path.symlink_to(outside)
    with pytest.raises(ValueError,match='symlink'):store.gc_apply(plan)
    assert outside.read_text()=='retained'
    path.unlink();os.link(outside,path)
    result=store.gc_apply(plan)
    assert not result['deleted'] and 'hardlinks' in result['skipped'][0]['reasons'][0]
    assert outside.read_text()=='retained'


def test_quota_blocks_before_provider_and_never_silently_gcs(settings,tmp_path,monkeypatch):
    item=query(settings,tmp_path);store=CacheStore(settings)
    settings.storage_policy['max_bytes']=0
    assert execute(settings,'sample')['cache_hit']
    called=[]
    monkeypatch.setattr('rdnascope.providers.json_query',lambda *a,**k:called.append(True))
    with pytest.raises(ValueError,match='budget blocked'):execute(settings,'sample','kernels')
    assert called==[] and store.path(item).exists()
    assert store.preflight(1)['status']=='blocked'
    assert not [l for i in store.inventory()['items'] for l in i['leases'] if l['active']]


def test_disk_floor_and_concurrent_reservations(settings,tmp_path,monkeypatch):
    store=CacheStore(settings);store.preflight()
    settings.storage_policy['max_bytes']=store.preflight()['cache_bytes']+1000000
    with store.lease('query:'+'a'*64,'writer',reserve=600000,writer=True):
        with pytest.raises(ValueError,match='budget blocked'):
            with store.lease('query:'+'b'*64,'writer',reserve=600000,writer=True):pass
    settings.storage_policy['max_bytes']=None;settings.storage_policy['min_free_bytes']=32
    from collections import namedtuple
    usage=namedtuple('usage','total used free')
    monkeypatch.setattr('rdnascope.lifecycle.shutil.disk_usage',lambda p:usage(64,48,16))
    assert store.preflight()['reasons']==['disk_reserve_would_be_violated']


def test_dead_and_reused_pid_lease_does_not_permanently_pin(settings,tmp_path):
    store=CacheStore(settings);item=query(settings,tmp_path)
    identity=process_identity();identity['start_ticks']='0'
    with store.locked() as c:
        c.execute('INSERT INTO leases VALUES(?,?,?,?,?,?,?)',('dead',item,json.dumps(identity),'stale',100000,0,1))
    assert store.preflight()['active_reserved_bytes']==0
    assert [i['id'] for i in store.gc_preview(0)['candidates']]==[item]
    assert store.reconcile()['dead_leases_removed']==1


def test_interrupted_delete_reconcile_retains_original_sha(settings,tmp_path):
    store=CacheStore(settings);item=query(settings,tmp_path)
    with store.locked() as c:c.execute("UPDATE items SET status='deleting' WHERE id=?",(item,))
    assert store.reconcile()['completed_tombstones']==[]
    store.path(item).unlink()
    assert store.reconcile()['completed_tombstones']==[item]
    assert store.inventory()['items'][0]['sha']


def test_namespace_exact_fingerprint_and_explicit_cold_condition(settings,fingerprint):
    first=namespaces.create(settings,fingerprint)
    assert namespaces.create(settings,fingerprint)['namespace']==first['namespace']
    changed=copy.deepcopy(fingerprint);changed['python_abi']='another-abi'
    other=namespaces.create(settings,changed)
    assert other['namespace']!=first['namespace']
    with pytest.raises(ValueError,match='fingerprint mismatch'):
        namespaces.check(CacheStore(settings),first['namespace'],changed)
    cold=namespaces.create(settings,fingerprint,'cold-control-1')
    assert cold['namespace']!=first['namespace']
    assert cold['namespace']==namespaces.create(settings,fingerprint,'cold-control-1')['namespace']
    incomplete=copy.deepcopy(fingerprint);del incomplete['sdk']
    with pytest.raises(ValueError):namespaces.create(settings,incomplete)


def test_pending_or_crashed_job_protects_namespace_during_lease_handoff(settings,fingerprint):
    store=CacheStore(settings);ns=namespaces.create(settings,fingerprint)['namespace']
    job='job:'+'c'*64
    store.create_directory(job,{'kind':'fixture'})
    with store.locked() as c:
        c.execute('INSERT INTO jobs(id,spec,status) VALUES(?,?,?)',(job,json.dumps({'namespace':ns}),'queued'))
    plan=store.gc_preview(0)
    assert not plan['candidates']
    assert all('active_or_unreconciled_job' in item['reasons'] for item in plan['protected'])
    assert store.reconcile()['abandoned_jobs']==[job]
    assert not store.gc_preview(0)['candidates']


def test_gc_owner_mismatch_and_cli_missing_plan_never_delete(settings,tmp_path):
    from rdnascope.cli import main
    store=CacheStore(settings);item=query(settings,tmp_path);plan=store.gc_preview(0)
    assert main(['--data-dir',str(settings.data_dir),'cache','gc','--execute'])==2
    retained=tmp_path/'retained-plan.json';retained.write_text('keep')
    assert main(['--data-dir',str(settings.data_dir),'cache','gc','--output',str(retained)])==2
    assert retained.read_text()=='keep'
    marker=store.meta/'owner.json';owner=json.loads(marker.read_text());owner['root']='wrong-root'
    marker.write_text(json.dumps(owner))
    with pytest.raises(ValueError,match='ownership/root mismatch'):store.gc_apply(plan)
    assert store.path(item).exists()


def test_lifecycle_unavailable_falls_back_to_uncached_query(settings,tmp_path,monkeypatch):
    item=query(settings,tmp_path)
    monkeypatch.setattr('rdnascope.lifecycle.fcntl',None)
    with pytest.raises(ValueError,match='Linux /proc'):execute(settings,'sample')
    result=execute(settings,'sample',cache=False)
    assert not result['cache_hit'] and result['rows'][0]['count']==1

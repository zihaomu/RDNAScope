import json
from pathlib import Path
import subprocess
import signal
import sys
import time

import pytest

from rdnascope.core import Settings
from rdnascope.lifecycle import CacheStore, process_alive, process_identity
from rdnascope import namespaces, workers


@pytest.fixture
def setup(tmp_path):
    settings=Settings(data_dir=tmp_path/'state')
    fp=json.loads((Path(__file__).parents[1]/'examples/cache-fingerprint.json').read_text())
    ns=namespaces.create(settings,fp)['namespace']
    return settings,fp,ns


def spec(fp,ns,code,**changes):
    return dict({'kind':'command','argv':[sys.executable,'-c',code],
        'namespace':ns,'fingerprint':fp,'namespace_reserve_bytes':1024*1024,
        'reserve_bytes':2*1024*1024,'log_bytes':1024*1024,'timeout_seconds':5,'max_rss_bytes':None},**changes)


def run(settings,fp,ns,code,**changes):
    job=workers.start(settings,spec(fp,ns,code,**changes))
    return workers.wait(settings,job['job'],15)


def test_compatible_namespace_reused_and_logs_sealed(setup):
    s,fp,ns=setup
    code='import os;from pathlib import Path;p=Path(os.environ["RDNASCOPE_COMPILE_CACHE"])/"compiled";print("hit" if p.exists() else "miss");p.write_text("fixture")'
    first=run(s,fp,ns,code);second=run(s,fp,ns,code)
    assert first['status']==second['status']=='passed'
    assert (Path(first['logs'])/'stdout.log').read_text().strip()=='miss'
    assert (Path(second['logs'])/'stdout.log').read_text().strip()=='hit'
    assert second['result']['scratch_cleaned'] and not second['child_alive']
    assert CacheStore(s).verify(ns)
    assert not [l for i in CacheStore(s).inventory()['items'] for l in i['leases'] if l['active']]


def test_timeout_kills_owned_descendants_and_pins_failure(setup,tmp_path):
    s,fp,ns=setup;report=tmp_path/'grandchild.json'
    code='import json,subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);Path('+repr(str(report))+').write_text(str(p.pid));time.sleep(30)'
    result=run(s,fp,ns,code,timeout_seconds=1)
    assert result['status']=='timeout' and not result['child_alive']
    assert not process_alive(process_identity(int(report.read_text())))
    assert not (Path(result['logs'])/'scratch').exists()
    item=next(i for i in CacheStore(s).inventory()['items'] if i['id']==ns)
    assert item['status']=='quarantined' and item['references']


def test_explicit_stop_and_unknown_process_protection(setup):
    s,fp,ns=setup
    started=workers.start(s,spec(fp,ns,'import time;time.sleep(30)',timeout_seconds=30))
    try:
        deadline=time.monotonic()+5
        while workers.status(s,started['job'])['status']=='queued' and time.monotonic()<deadline:time.sleep(.02)
        assert workers.status(s,started['job'])['child_alive']
        with pytest.raises(ValueError,match='Unknown managed'):workers.stop(s,'job:'+'f'*64)
    finally:
        workers.stop(s,started['job'])
        result=workers.wait(s,started['job'],10)
    assert result['status']=='canceled' and not result['child_alive']


def test_fast_exit_namespace_growth_and_logs_are_checked(setup):
    s,fp,ns=setup
    code='import os;from pathlib import Path;(Path(os.environ["RDNASCOPE_COMPILE_CACHE"])/"large").write_bytes(b"x"*65536)'
    result=run(s,fp,ns,code,namespace_reserve_bytes=1024)
    assert result['status']=='budget_blocked' and not result['child_alive']
    with pytest.raises(ValueError,match='not available'):namespaces.check(CacheStore(s),ns,fp)


def test_output_overflow_is_retained_as_bounded_failure(setup):
    s,fp,ns=setup
    result=run(s,fp,ns,'print("x"*65536)',log_bytes=1024)
    assert result['status']=='budget_blocked' and result['result']['log_truncated']
    assert sum(v['bytes'] for v in result['result']['logs'].values())<=1024
    assert not result['child_alive']


def test_foreign_namespace_writer_and_bad_abi_refused_before_launch(setup):
    s,fp,ns=setup;store=CacheStore(s)
    bad=dict(fp,python_abi='wrong')
    with pytest.raises(ValueError,match='fingerprint mismatch'):workers.start(s,spec(bad,ns,'pass'))
    with store.lease(ns,'active-writer',writer=True):
        with pytest.raises(ValueError,match='busy'):workers.start(s,spec(fp,ns,'pass'))
    assert workers.status(s)['jobs']==[]


def test_memory_limit_and_reused_supervisor_identity_guard(setup):
    s,fp,ns=setup
    started=workers.start(s,spec(fp,ns,'import time;time.sleep(30)',timeout_seconds=30))
    store=CacheStore(s)
    identity=None
    try:
        deadline=time.monotonic()+5
        while workers.status(s,started['job'])['status']=='queued' and time.monotonic()<deadline:time.sleep(.02)
        with store.locked() as c:
            identity=c.execute('SELECT supervisor FROM jobs WHERE id=?',(started['job'],)).fetchone()[0]
            reused=json.loads(identity);reused['start_ticks']='0'
            c.execute('UPDATE jobs SET supervisor=? WHERE id=?',(json.dumps(reused),started['job']))
        with pytest.raises(ValueError,match='identity is no longer live'):workers.stop(s,started['job'])
        assert workers.status(s,started['job'])['child_alive']
    finally:
        if identity:
            with store.locked() as c:c.execute('UPDATE jobs SET supervisor=? WHERE id=?',(identity,started['job']))
        workers.stop(s,started['job']);workers.wait(s,started['job'],10)
    # A fresh namespace after the canceled writer; no reuse of its quarantined state.
    ns=namespaces.create(s,fp,'rss-test')['namespace']
    result=run(s,fp,ns,'import time;x=bytearray(8*1024*1024);time.sleep(3)',max_rss_bytes=1024)
    assert result['status']=='budget_blocked' and result['result']['reason']=='rss_limit_exceeded'
    assert not result['child_alive']


def test_cli_interrupt_records_cancellation_and_cleans_owned_job(setup,tmp_path):
    s,fp,ns=setup;fingerprint=tmp_path/'fp.json';fingerprint.write_text(json.dumps(fp))
    proc=subprocess.Popen([sys.executable,'-m','rdnascope','--data-dir',str(s.data_dir),'cache','run',
        '--namespace',ns,'--fingerprint',str(fingerprint),'--reserve-bytes','1048576','--timeout-seconds','30',
        '--',sys.executable,'-c','import time;time.sleep(30)'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    job=None
    try:
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            jobs=workers.status(s)['jobs']
            if jobs and jobs[0]['status']=='running':job=jobs[0]['id'];break
            time.sleep(.02)
        assert job is not None
        proc.send_signal(signal.SIGINT)
        out,err=proc.communicate(timeout=15)
        assert proc.returncode==130 and json.loads(err)['status']=='canceled'
        result=workers.status(s,job)
        assert result['status']=='canceled' and not result['child_alive'] and not result['supervisor_alive']
    finally:
        if proc.poll() is None:proc.kill();proc.wait()
        if job and workers.status(s,job)['status'] in ('queued','running'):
            workers.stop(s,job);workers.wait(s,job,10)


def test_replaced_log_never_modifies_external_file(setup,tmp_path):
    s,fp,ns=setup;external=tmp_path/'external';external.write_text('keep original bytes')
    code='import os;from pathlib import Path;p=Path(os.environ["TMPDIR"]).parent/"stdout.log";p.unlink();p.symlink_to('+repr(str(external))+')'
    result=run(s,fp,ns,code)
    assert result['status']=='failed' and not result['child_alive']
    assert external.read_text()=='keep original bytes'
    inventory=CacheStore(s).inventory()
    assert inventory['budget']['status']=='blocked' and inventory['budget']['safety_errors']

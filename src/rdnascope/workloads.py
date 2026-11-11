"""Two workload result adapters, a bounded CPU demo and guarded external actions."""
from pathlib import Path
import platform
import sys

from .core import atomic_json, file_hash, identifier, object_hash, read_json
from .records import Records
from .lifecycle import CacheStore
from . import benchmark, workers, resources


def _job_ref(settings,job_id,relative,pointer=None,expected=None):
    path=CacheStore(settings).path(job_id)/relative
    ref={'source_id':'rdnascope-cache','relative_path':str(path.relative_to(settings.cache_dir)),'sha256':file_hash(path)}
    if pointer is not None:ref.update(json_pointer=pointer,expected=expected)
    return ref


def fixture(settings,contract_id,prefix,phase='aa'):
    identifier(prefix);store=Records(settings);contract=store.get('benchmark-contract',contract_id)['body']
    if contract['kind']!='cpu_fixture' or contract['basis']!='synthetic':raise ValueError('Built-in fixture requires an explicitly synthetic CPU contract')
    if set(contract['protocol']['cases'])!={'small','large'} or contract['metric']!={'name':'fixture_duration_ns','unit':'ns','direction':'lower'}:
        raise ValueError('Fixture contract cases/metric differ from the producer')
    script=Path(__file__).with_name('fixture_workload.py');p=contract['protocol']
    arms=['A']*p['boots'] if phase=='aa' else p['sequence']
    if not arms:raise ValueError('An explicit candidate sequence is required')
    measurements=[];jobs=[]
    for index,arm in enumerate(arms):
        boot=f'{prefix}-{index:03d}';variant='baseline' if arm=='A' else 'candidate'
        spec={'kind':'cpu-fixture','argv':[sys.executable,str(script),'--variant',variant,'--boot',boot,
              '--warmups',str(p['warmups']),'--repeats',str(p['repeats'])],
              'reserve_bytes':2*1024*1024,'log_bytes':1024*1024,'timeout_seconds':30,'max_rss_bytes':128*1024*1024}
        started=workers.start(settings,spec);job=workers.wait(settings,started['job'],45);jobs.append(job['id'])
        if job['status']!='passed':
            return {'status':'incomplete','measurements':measurements,'jobs':jobs,'failed_job':job['id'],'adopted':False}
        context={'workload_revision':file_hash(script),'runtime_digest':object_hash({'python':sys.version,'platform':platform.platform(),'executable':file_hash(Path(sys.executable))}),
                 'source_digest':file_hash(script),'device_set':['cpu'],'profiled':False,'cache_condition':'explicit warmup per independent process',
                 'variant':variant}
        ref=_job_ref(settings,job['id'],'outputs/metric.json');resource_ref=_job_ref(settings,job['id'],'result.json','/process_cleanup_passed',True)
        result=benchmark.ingest(settings,boot,contract_id,'metric-json',ref,boot,arm,context,resource_ref=resource_ref)
        measurements.append(result['id'])
    if phase=='aa':report=benchmark.aa(settings,measurements)
    else:
        a=[name for name,arm in zip(measurements,arms) if arm=='A'];b=[name for name,arm in zip(measurements,arms) if arm=='B']
        report=benchmark.compare(settings,a,b)
    return {'status':'completed','basis':'synthetic','measurements':measurements,'jobs':jobs,'report':report,
            'limits':['CPU fixture exercises the tool protocol only; no FreeToken/RDNA performance qualification']}


def external(settings,plan):
    """External launch is opt-in and ABI/profile bound. Never launch on occupied GPUs."""
    identifier(plan['run_id'])
    adapter=settings.adapters.get(plan['adapter'])
    if not isinstance(adapter,dict):raise ValueError('Adapter is not bound in the private machine profile')
    if adapter.get('gpu'):
        if not plan.get('physical_gpus'):raise ValueError('Explicit physical GPUs required')
        snap=resources.discover(settings,plan['physical_gpus'])
        if snap['status']!='available_snapshot_only':
            return {'schema_version':1,'status':'resource_blocked','run_id':plan['run_id'],'resources':snap,
                    'child_started':False,'adopted':False,'next':'Retry only after a fresh exclusive resource/identity check; no foreign stop'}
        if adapter.get('guard_protocol')!='locked-owner-observer-v1':
            raise ValueError('GPU adapter lacks the required locked resource/own-container cleanup protocol')
    executable=Path(adapter['executable']).expanduser().absolute()
    if not executable.is_file():raise ValueError('Adapter executable is missing')
    if file_hash(executable)!=adapter.get('executable_sha256'):raise ValueError('Adapter executable changed')
    for identity_file in adapter.get('identity_files',[]):
        if file_hash(Path(identity_file['path']))!=identity_file['sha256']:raise ValueError('Adapter implementation/bindings changed')
    if type(plan.get('timeout_seconds')) is not int or not 0<plan['timeout_seconds']<=3600 or type(plan.get('reserve_bytes')) is not int or plan['reserve_bytes']<=0:
        raise ValueError('Explicit time 1..3600s and positive disk budget required')
    arguments=plan.get('arguments',[])
    if adapter.get('actions'):
        action=plan.get('action')
        if action not in adapter['actions']:raise ValueError('Unsupported adapter action')
        values={'run_id':identifier(plan['run_id']),'physical_gpus':','.join(map(str,plan.get('physical_gpus',[]))),
                'timeout_seconds':str(plan['timeout_seconds'])}
        arguments=[a.replace('{run_id}',values['run_id']).replace('{physical_gpus}',values['physical_gpus']).replace('{timeout_seconds}',values['timeout_seconds']) for a in adapter['actions'][action]]
    elif adapter.get('gpu'):raise ValueError('GPU actions require fixed profile argument templates')
    if not isinstance(arguments,list) or not all(isinstance(a,str) for a in arguments):
        raise ValueError('Adapter arguments must be strings')
    # The private adapter is responsible for acquiring/rechecking its resource lease;
    # a discovery snapshot alone never constitutes a reservation.
    spec={'kind':'external-'+plan['adapter'],'argv':[str(executable),*arguments],
          'reserve_bytes':plan['reserve_bytes'],'log_bytes':min(plan['reserve_bytes'],1024*1024),
          'timeout_seconds':plan['timeout_seconds'],'max_rss_bytes':plan.get('max_rss_bytes'),
          'termination_grace_seconds':60 if adapter.get('gpu') else 2,'expand_output_dir':bool(adapter.get('actions'))}
    spec['adapter_identity']={'executable_sha256':adapter['executable_sha256'],'identity_files':adapter.get('identity_files',[]),'guard_protocol':adapter.get('guard_protocol')}
    spec['bound_inputs']=adapter.get('identity_files',[])
    if plan.get('namespace'):
        spec.update(namespace=plan['namespace'],fingerprint=read_json(Path(plan['fingerprint_file']),settings.max_json_bytes),
                    namespace_reserve_bytes=plan['namespace_reserve_bytes'])
    if plan.get('evidence_output',adapter.get('gpu',False)):spec['evidence_run']=plan['run_id']
    started=workers.start(settings,spec);job=workers.wait(settings,started['job'],plan['timeout_seconds']+90)
    CacheStore(settings).reference(job['id'],'workload:'+plan['run_id'])
    return {'schema_version':1,'status':job['status'],'run_id':plan['run_id'],'job':job,'adopted':False,
            'adapter_protocol':adapter.get('guard_protocol'),'limits':['Adapter GPU/collector/output gates require their own evidence; process exit alone is not qualification']}

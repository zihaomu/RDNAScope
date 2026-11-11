"""Pure-stdlib compatibility bridge, run by the bound legacy CPU interpreter.

Old application source/native/model evidence stays read-only. New output is under
the explicit RDNASCOPE_JOB_OUTPUT run. No declaration here qualifies live capture.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    sys.dont_write_bytecode=True
    p=argparse.ArgumentParser();p.add_argument('--bindings',type=Path,required=True)
    p.add_argument('--action',choices=['prepare','native-roi','aa','config-screen','optimize'],required=True);p.add_argument('--run',required=True)
    p.add_argument('--candidate-env',default='{}')
    p.add_argument('--prepared-dir',type=Path)
    p.add_argument('--physical-gpus');p.add_argument('--budget-seconds',type=int,default=1800)
    args=p.parse_args();bindings=json.loads(args.bindings.read_text());output=Path(os.environ['RDNASCOPE_JOB_OUTPUT']).resolve()
    if not args.run or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-' for c in args.run):raise ValueError('Invalid run ID')
    for name,expected in bindings['identity_files'].items():
        if sha(name)!=expected:raise ValueError('Bound compatibility input changed: '+name)
    foundation=json.loads(Path(bindings['foundation_lock']).read_text())
    if foundation['rocm_release']!='10.1.0':raise ValueError('This compatibility profile requires the locked ROCm 10.1 foundation')
    sys.path.insert(0,str(Path(bindings['legacy_root'])/'src'))
    from tlp import collection,optimization
    from tlp.experiment import Runtime
    collection.FOUNDATION=Path(bindings['foundation_lock']);collection.RESERVATIONS=Path(bindings['reservation_dir']);collection.LAUNCHER=Path(bindings['launcher'])
    root=Path(bindings['legacy_root']);physical=[int(v) for v in args.physical_gpus.split(',')] if args.physical_gpus else []
    def interrupted(signum,frame):raise InterruptedError('Owned adapter interrupted: '+str(signum))
    for signum in (signal.SIGTERM,signal.SIGINT):signal.signal(signum,interrupted)
    (output/'bindings-snapshot.json').write_text(json.dumps(bindings,indent=2)+'\n')
    owner_path=output/'artifacts'/args.run
    try:
        if args.action=='prepare':
            result=optimization.prepare(args.run,output/'artifacts')
        elif args.action=='optimize':
            if not args.prepared_dir:raise ValueError('An explicit prepared candidate directory is required')
            prepared=args.prepared_dir.resolve(strict=True)
            target=owner_path;target.mkdir(parents=True)
            for name in ('identity.json','plan.json','candidate.patch','baseline-source-manifest.json','candidate-source-manifest.json','runner-source-manifest.json','prompts.json','oracle.json'):
                shutil.copy2(prepared/name,target/name)
            shutil.copytree(prepared/'source',target/'source')
            plan=json.loads((target/'plan.json').read_text());plan['run']=args.run
            (target/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
            identity=json.loads((target/'identity.json').read_text());identity['plan_sha256']=sha(target/'plan.json')
            (target/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
            source=Path(optimization.__file__).read_text()
            source=source.replace('import difflib\n','import difflib\nimport os\n',1)
            needle="cache = folder / 'cache'\n    cache.mkdir()"
            if source.count(needle)!=1:raise ValueError('Legacy cache binding changed; requalify the bridge')
            source=source.replace(needle,"cache = Path(os.environ['RDNASCOPE_COMPILE_CACHE'])\n    cache.mkdir(exist_ok=True)")
            runner=output/'bound-optimization.py';runner.write_text(source)
            shutil.copy2(root/'src/tlp/experiment.py',output/'experiment.py')
            frozen=importlib.util.spec_from_file_location('tlp.rdnascope_bound_optimization',runner)
            module=importlib.util.module_from_spec(frozen);frozen.loader.exec_module(module)
            (output/'runner-binding.json').write_text(json.dumps({'original_sha256':sha(optimization.__file__),'bound_sha256':sha(runner),
                'change':'Bind only cache root to the exclusive declared ABI namespace; original source untouched','prepared_from':str(prepared)},indent=2)+'\n')
            result=module.execute(args.run,physical,args.budget_seconds,output/'artifacts')
        elif args.action=='native-roi':
            # Bind the frozen controller to a new output root; original source is
            # not patched and every frozen helper/runtime digest is recorded.
            (output/'scripts').mkdir();(output/'locks').mkdir()
            for name in ('p5_opt_run_boot.py','p5_app_identity.py','audit_official_trace.py'):
                shutil.copy2(root/'scripts'/name,output/'scripts'/name)
            shutil.copytree(root/'scripts/p5_native_hooks',output/'scripts/p5_native_hooks',ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copy2(root/'locks/freetoken-p5-environment.json',output/'locks/freetoken-p5-environment.json')
            cache=Path(os.environ['RDNASCOPE_COMPILE_CACHE']) if os.environ.get('RDNASCOPE_COMPILE_CACHE') else output/'new-cache'
            cache.mkdir(exist_ok=True)
            stub=output/'artifacts/tp2opt-20261110-native05';stub.mkdir(parents=True)
            (stub/'plan.json').write_text(json.dumps({'cache_source':str(cache)}))
            controller=root/'scripts/official_tp2_capture.py'
            shutil.copy2(controller,output/'controller-source.py')
            spec=importlib.util.spec_from_file_location('rdnascope_frozen_controller',controller)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            module.ROOT=output
            result=module.execute(args.run,physical)
        else:
            folder=owner_path;folder.mkdir(parents=True)
            source=folder/'source';source.mkdir()
            for name in ('p5_opt_run_boot.py','p5_app_identity.py'):shutil.copy2(root/'scripts'/name,source/name)
            candidate_env=json.loads(args.candidate_env)
            if set(candidate_env)-{'OMP_NUM_THREADS','FREETOKEN_ROW_STORE_READER_THREADS'} or any(not isinstance(v,str) or not v.isdigit() or not 1<=int(v)<=64 for v in candidate_env.values()):
                raise ValueError('Only explicit bounded OMP/reader thread candidates are supported by this bridge')
            if args.action=='config-screen':
                harness=source/'p5_opt_run_boot.py';text=harness.read_text()
                needle='server_env=dict(os.environ,**server_overrides)'
                if text.count(needle)!=1:raise ValueError('Harness configuration injection point changed')
                harness.write_text(text.replace(needle,needle+'\nserver_env.update(cfg.get("candidate_env",{}))'))
                (folder/'harness-binding.json').write_text(json.dumps({'original_sha256':sha(root/'scripts/p5_opt_run_boot.py'),'bound_sha256':sha(harness),
                    'candidate_env':candidate_env,'scope':'Same copied harness for both arms; model/native source unchanged'},indent=2)+'\n')
            shutil.copy2(optimization.PREP/'source-manifest.json',folder/'source-manifest.json')
            prompts=[json.loads((optimization.OLD/'numeric-prompts.json').read_text())[0]]+[r for r in json.loads((optimization.OLD/'extended-prompts.json').read_text()) if r['name'] in ('en2048','long8000')]
            (folder/'prompts.json').write_text(json.dumps(prompts));shutil.copy2(optimization.OLD/'runs/perf-controlled-tp1-1/performance.json',folder/'oracle.json')
            cache=Path(os.environ['RDNASCOPE_COMPILE_CACHE']) if os.environ.get('RDNASCOPE_COMPILE_CACHE') else folder/'cache'
            cache.mkdir(exist_ok=True)
            with Runtime(folder,physical,args.budget_seconds) as runtime:
                runtime.foundation();runtime.job('identity',optimization.BASELINE,folder,['python','/experiment-source/p5_app_identity.py'],optimization.IMAGE,optimization.MODEL,cache,90)
                cohorts={}
                def boot(label,variant):
                    run=folder/'runs'/label;run.mkdir(parents=True)
                    (run/'config.json').write_text(json.dumps({'tp':2,'profile':False,'measured_repeats':3,'port':19981,'fixed_moe_slots':14500,'env':{},'candidate_env':candidate_env if variant=='B' else {}}))
                    runtime.job(label,optimization.BASELINE,folder,['python','/experiment-source/p5_opt_run_boot.py',label],optimization.IMAGE,optimization.MODEL,cache,900)
                    rows=json.loads((run/'performance.json').read_text())
                    if len(rows)!=12 or not all(r['output_matches_frozen_oracle'] for r in rows):raise ValueError('Model output/request contract failed')
                    cohorts[label]=rows
                for label in ('AA1','AA2','AA3'):boot(label,'A')
                aa=optimization.aa_result(cohorts);(folder/'aa.json').write_text(json.dumps(aa,indent=2)+'\n')
                screen=None
                if args.action=='config-screen' and aa['passed']:
                    for label,variant in [('A1','A'),('B1','B'),('B2','B'),('A2','A')]:boot(label,variant)
                    screen=optimization.screen_result(cohorts);(folder/'screen.json').write_text(json.dumps(screen,indent=2)+'\n')
            result={'status':'completed_three_trace_off_boots','performance_files':[str(p) for p in (folder/'runs').glob('*/performance.json')],
                    'aa_passed':aa['passed'],'config_screen':screen or {'status':'not_run'},'adopted':False,
                    'normal_performance_qualified':False,'next':'ingest raw observations and evaluate the separately frozen measurement contract; screening is not adoption'}
        (output/'adapter-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:
        # The shared foundation launcher has no project label. An exact unique
        # output path in its immutable command identifies only this foundation job.
        stopped=[]
        ids=subprocess.run(['docker','ps','-q','--filter','ancestor='+foundation['image']['id']],capture_output=True,text=True,timeout=10).stdout.split()
        for cid in ids:
            info=json.loads(subprocess.check_output(['docker','inspect',cid],text=True,timeout=10))[0]
            command=info.get('Config',{}).get('Cmd') or []
            if any(str(owner_path/'foundation.json') in argument for argument in command):
                subprocess.run(['docker','stop','--timeout','3',cid],capture_output=True,timeout=15,check=True);stopped.append(cid)
        (output/'bridge-cleanup.json').write_text(json.dumps({'stopped_exact_owned_foundation_containers':stopped,'foreign_processes_stopped':False},indent=2)+'\n')

if __name__=='__main__':main()

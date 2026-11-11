"""Small standard-library workload; GPU/model/compiler qualification is out of scope."""
import argparse
import json
import os
from pathlib import Path
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--variant',choices=['baseline','candidate'],required=True)
    p.add_argument('--boot',required=True);p.add_argument('--warmups',type=int,required=True);p.add_argument('--repeats',type=int,required=True)
    args=p.parse_args();samples=[]
    for case,n in [('small',128),('large',512)]:
        expected=n*(n-1)*(2*n-1)//6
        for repeat in range(args.warmups+args.repeats):
            start=time.perf_counter_ns()
            for _ in range(64):
                if args.variant=='baseline':actual=sum([i*i for i in range(n)])
                else:actual=sum(i*i for i in range(n))
            elapsed=time.perf_counter_ns()-start
            samples.append({'case':case,'repeat':repeat,'warmup':repeat<args.warmups,'ok':True,
                            'value':elapsed/64,'actual_output':actual,'expected_output':expected})
    result={'schema_version':1,'metric':{'name':'fixture_duration_ns','unit':'ns','direction':'lower'},
            'boot':args.boot,'variant':args.variant,'samples':samples,'scope':'CPU fixture mechanics; no model/GPU gain'}
    output=Path(os.environ['RDNASCOPE_JOB_OUTPUT'])/'metric.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'output':'metric.json','numeric_passed':all(s['actual_output']==s['expected_output'] for s in samples)}))

if __name__=='__main__':main()

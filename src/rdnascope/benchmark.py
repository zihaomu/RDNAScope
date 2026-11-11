"""Explicit metrics, independent boot statistics and conservative matched comparison."""
from collections import defaultdict
import math
from statistics import median

from .core import object_hash, read_json, validate
from .records import Records, evidence

MATCH_KEYS={
 'model':('workload_revision','runtime_digest','source_digest','input_set_sha256','precision','tp','ep','graph','concurrency','output_tokens','cache_condition','threads','device_set','profiled','token_semantics'),
 'kernel':('device_gfx','runtime_digest','compiler','precision','shape','layout','timing','cache_condition','profiled'),
 'communication':('device_set','topology','collective','dtype','payload_bytes','concurrency','runtime_digest','timing','profiled'),
 'cpu_fixture':('workload_revision','runtime_digest','source_digest','device_set','profiled','cache_condition')}
METRICS={
 'http_wall_seconds':('s','lower',lambda e:e['wall_seconds']),
 'http_first_text_seconds':('s','lower',lambda e:e.get('first_text_seconds')),
 'server_decode_tokens_per_second':('token/s','higher',lambda e:e.get('timings',{}).get('predicted_per_second')),
 'server_decode_ms_per_token':('ms/token','lower',lambda e:e.get('timings',{}).get('predicted_per_token_ms')),
 'cpu_seconds_per_output_token':('s/token','lower',lambda e:e.get('cpu_seconds_per_output_token'))}

def numeric_output(value):
    return type(value) in (int,float) and math.isfinite(value) or isinstance(value,list) and bool(value) and all(numeric_output(v) for v in value)


def register_contract(settings,name,body,refs=None):
    validate('benchmark-contract',body)
    missing=set(MATCH_KEYS[body['kind']])-set(body['match_keys'])
    if missing:raise ValueError('Contract missing comparison dimensions: '+','.join(sorted(missing)))
    if not set(body['intentional_changes'])<=set(body['match_keys']):raise ValueError('Intentional changes must be comparison dimensions')
    sequence=body['protocol']['sequence']
    if sequence and (sequence.count('A')!=sequence.count('B') or len(sequence)%2):
        raise ValueError('Candidate sequence must contain balanced arms and complete pairs')
    if body['protocol']['classification']=='formal' and (len(sequence)<6 or not {'AB','BA'}<={''.join(sequence[i:i+2]) for i in range(0,len(sequence),2)}):
        raise ValueError('Formal comparison needs at least three preregistered pairs with both orders')
    return Records(settings).add('benchmark-contract',name,body,refs)


def _input(settings,ref):
    evidence(settings,ref)
    return read_json((settings.source_roots[ref['source_id']]/ref['relative_path']).resolve(),settings.max_json_bytes)


def ingest(settings,name,contract_id,adapter,input_ref,boot,arm,context,oracle_ref=None,resource_ref=None):
    store=Records(settings);contract=store.get('benchmark-contract',contract_id)['body']
    data=_input(settings,input_ref);refs=[input_ref]
    oracle=_input(settings,oracle_ref) if oracle_ref else None
    if oracle_ref:refs.append(oracle_ref)
    samples=[];audit='reported_only'
    if adapter=='freetoken-http':
        metric=METRICS.get(contract['metric']['name'])
        if not metric or metric[:2]!=(contract['metric']['unit'],contract['metric']['direction']):
            raise ValueError('Unsupported HTTP metric/unit/direction; first-text is not TTFT and chunks are not token ITL')
        if not isinstance(data,list):raise ValueError('FreeToken HTTP adapter expects an observation array')
        references=defaultdict(set)
        if oracle is not None:
            for row in oracle:
                references[row['case']].add((row.get('text_sha256'),row.get('usage',{}).get('completion_tokens')))
        for row in data:
            value=metric[2](row)
            correct=None
            if oracle is not None:
                output=(row.get('text_sha256'),row.get('usage',{}).get('completion_tokens'))
                correct=bool(output[0]) and output in references[row['case']]
            samples.append({'case':row['case'],'repeat':row['repeat'],'warmup':row['warmup'],
                'ok':type(value) in (int,float) and math.isfinite(value) and value>=0,
                'value':value,'output_correct':correct,
                'detail':{'reported_output_match':row.get('output_matches_frozen_oracle'),
                          'output_tokens':row.get('usage',{}).get('completion_tokens'),
                          'first_text_is_ttft':False,'sse_chunk_intervals_are_token_itl':False}})
        if oracle is not None:audit='verified' if all(s['output_correct'] for s in samples) else 'failed'
    elif adapter=='metric-json':
        if not isinstance(data,dict) or data.get('schema_version')!=1 or data.get('metric')!=contract['metric']:
            raise ValueError('Metric JSON needs schema_version=1 and the exact metric contract')
        for row in data['samples']:
            value=row['value']
            correct=(numeric_output(row['actual_output']) and numeric_output(row['expected_output']) and object_hash(row['actual_output'])==object_hash(row['expected_output'])) if 'actual_output' in row and 'expected_output' in row else None
            samples.append({'case':row['case'],'repeat':row['repeat'],'warmup':row['warmup'],
                'ok':row.get('ok') is True and type(value) in (int,float) and math.isfinite(value) and value>=0,
                'value':value,'output_correct':correct,'detail':{'output_check_scope':'fixture producer numeric comparison; not a model oracle'}})
        audit='verified' if samples and all(s['output_correct'] is True for s in samples) else 'failed' if any(s['output_correct'] is False for s in samples) else 'unknown'
    else:raise ValueError('Unknown workload result adapter')
    resource='unknown'
    if resource_ref:
        evidence(settings,resource_ref);refs.append(resource_ref)
        if 'json_pointer' not in resource_ref or type(resource_ref.get('expected')) is not bool:
            raise ValueError('Resource audit requires a typed boolean evidence assertion')
        resource='verified' if resource_ref['expected'] else 'contaminated'
    basis=contract['basis']
    body={'schema_version':1,'basis':basis,'contract_id':contract_id,'adapter':adapter,'boot':boot,'arm':arm,
          'context':context,'samples':samples,'output_audit':audit,'resource_audit':resource,
          'collection_status':'complete' if samples and all(s['ok'] for s in samples) else 'failed'}
    return store.add('measurement',name,body,refs)


def _cohort(settings,ids):
    if not ids or len(set(ids))!=len(ids):raise ValueError('Explicit distinct measurement IDs are required')
    store=Records(settings);records=[store.get('measurement',n) for n in ids]
    contracts={r['body']['contract_id'] for r in records}
    if len(contracts)!=1:raise ValueError('Measurement cohorts use different contracts')
    contract_record=store.get('benchmark-contract',next(iter(contracts)))
    return contract_record,records


def _groups(contract,records):
    values=defaultdict(dict);issues=[];seen=set();input_hashes=set()
    p=contract['protocol']
    for record in records:
        m=record['body'];boot=m['boot']
        if boot in seen:issues.append('duplicate_boot:'+boot)
        seen.add(boot)
        source_hash=record['evidence'][0]['sha256'] if record['evidence'] else None
        if source_hash is None:issues.append('missing_boot_input_evidence:'+boot)
        elif source_hash in input_hashes:issues.append('reused_input_for_independent_boot:'+boot)
        input_hashes.add(source_hash)
        if m['collection_status']!='complete':issues.append('incomplete_or_failed_boot:'+boot)
        for case in p['cases']:
            rows=[s for s in m['samples'] if s['case']==case]
            measured=[s for s in rows if not s['warmup']]
            warmups=[s for s in rows if s['warmup']]
            if len(measured)!=p['repeats'] or len(warmups)!=p['warmups'] or len({s['repeat'] for s in rows})!=len(rows):
                issues.append('sample_count_or_repeat_mismatch:'+boot+':'+case)
            if measured and all(s['ok'] and type(s['value']) in (int,float) and math.isfinite(s['value']) for s in measured):
                values[case][boot]=median(s['value'] for s in measured)
            else:issues.append('invalid_metric_sample:'+boot+':'+case)
        if any(s['case'] not in p['cases'] for s in m['samples']):issues.append('unexpected_case:'+boot)
    return values,issues


def aa(settings,ids):
    contract_record,records=_cohort(settings,ids);contract=contract_record['body'];p=contract['protocol']
    values,issues=_groups(contract,records)
    contexts=[r['body']['context'] for r in records]
    for key in contract['match_keys']:
        if any(c.get(key) is None for c in contexts):issues.append('unknown_condition:'+key)
        elif len({object_hash(c[key]) for c in contexts})>1:issues.append('unmatched_condition:'+key)
    if len(records)!=p['boots']:issues.append('independent_boot_count')
    for r in records:
        m=r['body']
        if m['context'].get('profiled') is not False:issues.append('trace_off_not_proven:'+r['id'])
        if m['output_audit']!='verified':issues.append('output_unqualified:'+r['id'])
        if m['resource_audit']!='verified':issues.append('resource_unqualified:'+r['id'])
    gates=[]
    for case in p['cases']:
        samples=list(values.get(case,{}).values())
        middle=median(samples) if samples else None
        spread=(max(samples)-min(samples))/middle if middle and len(samples)>1 else None
        passed=spread is not None and spread<=p['max_aa_spread'] and len(samples)==p['boots']
        gates.append({'case':case,'boot_medians':values.get(case,{}),'relative_range':spread,'passed':passed})
    passed=not issues and all(g['passed'] for g in gates)
    return {'schema_version':1,'status':'passed' if passed else 'inconclusive','passed':passed,
            'contract_id':contract_record['id'],'contract_sha256':contract_record['record_sha256'],
            'measurements':[{'id':r['id'],'record_sha256':r['record_sha256']} for r in records],
            'issues':sorted(set(issues)),'gates':gates,'unit':'independent_boot_median',
            'limits':['No reliable production P95/ITL/noise model inferred','All failed/missing samples retained; no retry-to-pass']}


def compare(settings,baseline_ids,candidate_ids):
    contract_record,base=_cohort(settings,baseline_ids);other,target=_cohort(settings,candidate_ids)
    if contract_record['record_sha256']!=other['record_sha256']:raise ValueError('Comparisons require the same immutable contract')
    contract=contract_record['body'];p=contract['protocol'];intentional=[];issues=[]
    for key in contract['match_keys']:
        a=[r['body']['context'].get(key) for r in base];b=[r['body']['context'].get(key) for r in target]
        if any(v is None for v in a+b):issues.append('unknown_condition:'+key);continue
        if len({object_hash(v) for v in a})!=1 or len({object_hash(v) for v in b})!=1:issues.append('within_arm_mismatch:'+key)
        elif a[0]!=b[0]:
            if key in contract['intentional_changes']:intentional.append({'key':key,'baseline':a[0],'candidate':b[0]})
            else:issues.append('unintended_condition_change:'+key)
    aa_base=aa(settings,baseline_ids);aa_target=aa(settings,candidate_ids)
    if p['classification']=='screening':
        for arm,result,records in [('A',aa_base,base),('B',aa_target,target)]:
            expected=p['sequence'].count(arm)
            if expected>=2 and len(records)==expected:
                result['issues']=[i for i in result['issues'] if i!='independent_boot_count']
                for gate in result['gates']:
                    gate['passed']=len(gate['boot_medians'])==expected and gate['relative_range'] is not None and gate['relative_range']<=p['max_aa_spread']
                result['passed']=not result['issues'] and all(g['passed'] for g in result['gates'])
                result['status']='passed' if result['passed'] else 'inconclusive'
                result['scope']='screening arm stability only; separate preregistered baseline A/A still required'
    if not aa_base['passed'] or not aa_target['passed']:issues.append('aa_unqualified')
    a,ai=_groups(contract,base);b,bi=_groups(contract,target);issues+=ai+bi
    ordered=sorted(base+target,key=lambda r:r['body']['boot'])
    sequence=[r['body']['arm'] for r in ordered]
    if sequence!=p['sequence']:issues.append('preregistered_sequence_mismatch')
    if any(r['body']['arm']!='A' for r in base) or any(r['body']['arm']!='B' for r in target):issues.append('arm_labels_mismatch')
    gates=[]
    ambiguous=False
    for case in p['cases']:
        av=list(a.get(case,{}).values());bv=list(b.get(case,{}).values())
        am=median(av) if av else None;bm=median(bv) if bv else None
        ratio=bm/am if am and bm is not None else None
        gain=(1-ratio if contract['metric']['direction']=='lower' else ratio-1) if ratio is not None else None
        pair_ratios=[]
        for index in range(0,len(ordered)-1,2):
            pair=ordered[index:index+2]
            pair_a=next((r for r in pair if r['body']['arm']=='A'),None);pair_b=next((r for r in pair if r['body']['arm']=='B'),None)
            if pair_a and pair_b:
                x=a.get(case,{}).get(pair_a['body']['boot']);y=b.get(case,{}).get(pair_b['body']['boot'])
                if x and y is not None:pair_ratios.append(y/x)
        pair_gains=[1-r if contract['metric']['direction']=='lower' else r-1 for r in pair_ratios]
        pair_ok=bool(pair_gains) and min(pair_gains)>=p['min_gain']
        ambiguous=ambiguous or bool(pair_gains and min(pair_gains)<p['min_gain']<=max(pair_gains))
        gates.append({'case':case,'baseline_boot_median':am,'candidate_boot_median':bm,'candidate_over_baseline':ratio,
                      'relative_gain':gain,'paired_ratios':pair_ratios,'observed_pair_gain_range':[min(pair_gains),max(pair_gains)] if pair_gains else None,
                      'passed':gain is not None and gain>=p['min_gain'] and pair_ok})
    status='inconclusive' if issues or ambiguous else 'passed' if all(g['passed'] for g in gates) else 'rejected'
    return {'schema_version':1,'status':status,'passed':status=='passed','classification':p['classification'],
            'intentional_changes':intentional,'issues':sorted(set(issues)),'gates':gates,
            'aa_baseline':aa_base,'aa_candidate':aa_target,'adopted':False,
            'limits':['Screening is not formal adoption','Independent output/numerical scope and source adoption remain separate',
                      'Ratios are descriptive until matching/stability gates pass; no counter subtraction',
                      'Observed pair range is not a population confidence interval']}


def register_reference(settings,name,body,refs=None):
    validate('reference',body)
    required=set(MATCH_KEYS[body['kind']])-{'source_digest','input_set_sha256','profiled','token_semantics'}
    if not required<=set(body['match_keys']):raise ValueError('Reference omits applicable dimensions')
    if body['qualification']=='qualified':
        if body['basis']=='synthetic' or body['basis']=='declaration' and body['reference_type']!='specification_bound' or not refs or body['value'] is None or any(body['context'].get(k) is None for k in body['match_keys']):
            raise ValueError('Qualified reference needs measured evidence and complete context')
        if body['reference_type']=='reachable_calibration' and not body['capability_id']:
            raise ValueError('Reachable GPU calibration requires a matching capability record')
        if body['reference_type']!='specification_bound':
            if not body['measurement_ids']:raise ValueError('Measured references require explicit measurement records')
            measured_contract,measurements=_cohort(settings,body['measurement_ids'])
            mc=measured_contract['body']
            if mc['kind']!=body['kind'] or mc['basis']!=body['basis'] or mc['metric']['name']!=body['metric'] or mc['metric']['unit']!=body['unit']:
                raise ValueError('Reference and measurement kind/basis/metric mismatch')
            if not aa(settings,body['measurement_ids'])['passed']:raise ValueError('Reference measurement stability/output/resource gates failed')
            case=body['context'].get('case')
            if any((case if k=='case' and case in mc['protocol']['cases'] else m['body']['context'].get(k))!=body['context'].get(k) for m in measurements for k in body['match_keys']):
                raise ValueError('Reference context differs from its measured conditions')
            groups,_=_groups(mc,measurements)
            if len(groups)!=1 and (case not in groups or 'case' not in body['match_keys']):raise ValueError('A multi-case reference requires an explicit matched case')
            observed=median((groups[case] if case in groups else next(iter(groups.values()))).values())
            if not math.isclose(observed,body['value'],rel_tol=1e-12,abs_tol=0):raise ValueError('Reference value does not match the scoped measured median')
        if body['capability_id']:
            capability=Records(settings).get('capability',body['capability_id'])['body']
            feature='kernel_timing' if body['kind']=='kernel' else 'communication_timing' if body['kind']=='communication' else 'normal_performance'
            if body['reference_type']=='reachable_calibration' and (capability['features'].get(feature,{}).get('status')!='qualified' or
                capability['context'].get('runtime_digest')!=body['context'].get('runtime_digest') or
                body['kind']=='kernel' and capability['context'].get('gfx')!=body['context'].get('device_gfx')):
                raise ValueError('Calibration capability is not qualified for this timing/runtime/device context')
    return Records(settings).add('reference',name,body,refs)


def reference_match(settings,name,context):
    r=Records(settings).get('reference',name);body=r['body']
    unknown=[k for k in body['match_keys'] if body['context'].get(k) is None or context.get(k) is None]
    different=[k for k in body['match_keys'] if k not in unknown and body['context'][k]!=context[k]]
    applicable=not unknown and not different and body['qualification']=='qualified'
    return {'reference_id':name,'record_sha256':r['record_sha256'],'applicable':applicable,
            'unknown_conditions':unknown,'different_conditions':different,'reference_type':body['reference_type'],
            'value':body['value'] if applicable else None,'unit':body['unit'],
            'limits':['Specification bound is not reachable performance','Unknown shape/layout/runtime never yields a roofline']}

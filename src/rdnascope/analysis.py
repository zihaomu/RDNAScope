"""Scoped Model/Kernel/Multi-GPU findings; never manufacture missing critical paths."""
from collections import defaultdict
from statistics import median

from .core import object_hash, validate
from .records import Records, evidence
from .query import execute
from .storage import Registry
from .benchmark import reference_match, aa


def register_map(settings,name,body):
    validate('semantic-map',body);registered=Registry(settings).inspect(body['run_id'])
    available={a['artifact_id'] for a in registered['artifacts']}
    if not set(body['input_artifacts'])<=available:raise ValueError('Semantic map references unregistered inputs')
    seen=set();refs=[]
    for row in body['entries']:
        if not row.get('event_id') or row['event_id'] in seen:raise ValueError('Semantic event IDs must be explicit and unique')
        if row['event_id'].split('#',1)[0] not in body['input_artifacts']:raise ValueError('Semantic event escaped its declared artifact')
        if row.get('association') not in ('exact','inferred','unmapped'):raise ValueError('Unknown association status')
        if row['association']=='exact':
            proof=row.get('proof')
            if not proof or proof.get('expected') is not True or 'json_pointer' not in proof:raise ValueError('Exact semantic association requires a typed true proof')
            evidence(settings,proof);refs.append(proof)
        elif row.get('proof'):
            evidence(settings,row['proof']);refs.append(row['proof'])
        seen.add(row['event_id'])
    graph=defaultdict(list)
    for edge in body['dependencies']:
        if edge.get('source') not in seen or edge.get('target') not in seen:raise ValueError('Dependency endpoint missing')
        if edge.get('association')!='exact' or not edge.get('proof'):raise ValueError('Dependency edges need explicit exact proofs')
        if edge['proof'].get('expected') is not True or 'json_pointer' not in edge['proof']:raise ValueError('Dependency proof must assert true')
        evidence(settings,edge['proof']);refs.append(edge['proof']);graph[edge['source']].append(edge['target'])
    def visit(node,active,done):
        if node in active:raise ValueError('Dependency graph contains a cycle')
        if node in done:return
        for target in graph[node]:visit(target,active|{node},done)
        done.add(node)
    done=set()
    for node in list(graph):visit(node,set(),done)
    if body['clock'].get('calibrated'):
        proof=body['clock'].get('proof');uncertainty=body['clock'].get('uncertainty_ns')
        if not proof or proof.get('expected') is not True or 'json_pointer' not in proof or type(uncertainty) is not int or uncertainty<0:
            raise ValueError('Clock calibration requires evidence and nonnegative integer uncertainty')
        evidence(settings,proof);refs.append(proof)
        capability_id=body['clock'].get('capability_id')
        if not capability_id:raise ValueError('Qualified clock mapping requires a scoped capability record')
        cap=Records(settings).get('capability',capability_id)
        ctx=cap['body']['context'];env=registered['identity']['environment']['digest'];world=registered['identity']['workload']['tp']
        if cap['body']['features'].get('cross_rank_clock',{}).get('status')!='qualified' or env is None or world is None or ctx.get('runtime_digest')!=env or ctx.get('world')!=world:
            raise ValueError('Clock capability runtime/world is not qualified for this run')
        if set(ctx.get('input_artifacts',[]))!=set(body['input_artifacts']) or type(ctx.get('clock_uncertainty_ns')) is not int or ctx['clock_uncertainty_ns']>uncertainty:
            raise ValueError('Clock capability input scope/error bound mismatch')
        refs+=cap['evidence']
    if body['scope_complete']:
        proof=body['clock'].get('scope_proof')
        if not proof or proof.get('expected') is not True or 'json_pointer' not in proof:raise ValueError('Scope completeness needs independent proof')
        evidence(settings,proof);refs.append(proof)
    return Records(settings).add('semantic-map',name,body,refs)


def _events(settings,run,provider,artifacts,max_rows=100000):
    rows=[];queries=[];first=None
    while True:
        q=execute(settings,run,'events',provider,limit=1000,offset=len(rows),cache=False,artifact_ids=artifacts)
        if q['provenance']['provider']['name']=='http':
            q=execute(settings,run,'metrics',provider,limit=1000,offset=len(rows),cache=False,artifact_ids=artifacts)
        first=first or q;rows.extend(q['rows']);queries.append(q['query_id'])
        if len(rows)>max_rows:raise ValueError('Analysis event budget exceeded; register a smaller official window')
        if not q['page']['has_more']:return rows,queries,first


def analyze(settings,run,output_prefix,provider='auto',artifacts=None,semantic_map=None,references=None,measurement_ids=None):
    registered=Registry(settings).inspect(run);store=Records(settings)
    rows,queries,envelope=_events(settings,run,provider,artifacts)
    semantic={};clock={};map_record=None
    if semantic_map:
        map_record=store.get('semantic-map',semantic_map);mapping=map_record['body']
        if mapping['run_id']!=run or set(mapping['input_artifacts'])!=set(envelope['provenance']['inputs']) or mapping['provider']!=envelope['provenance']['provider']:
            raise ValueError('Semantic map run/artifact/provider build mismatch')
        event_ids={r['event_id'] for r in rows}
        if any(e['event_id'] not in event_ids for e in mapping['entries']):raise ValueError('Semantic map contains absent native event locators')
        semantic={r['event_id']:r for r in mapping['entries']};clock=mapping['clock']
    basis='synthetic' if registered['identity']['role']=='fixture' else registered['identity']['extensions'].get('observation_basis','historical_reanalysis')
    findings=[]
    def add(domain,observation,position,ev,limits,next_experiment,numeric_gap=None,reference=None,alternatives=None):
        body={'schema_version':1,'basis':basis,'run_id':run,'domain':domain,'status':'diagnostic',
              'observation':observation,'position':position,'reference':reference,'evidence':ev,
              'limits':limits,'alternatives':alternatives or [],'next_experiment':next_experiment,
              'numeric_gap':numeric_gap,'recoverable_wall_ns':None}
        name=output_prefix+'-'+str(len(findings)+1)
        saved=store.add('finding',name,body,map_record['evidence'] if map_record else None)
        findings.append({'id':name,'record_sha256':saved['record_sha256'],**body})
    base_evidence=[{'query_ids':queries,'inputs':envelope['provenance']['inputs'],'provider':envelope['provenance']['provider']}]
    if map_record:base_evidence.append({'semantic_map':{'id':map_record['id'],'record_sha256':map_record['record_sha256']}})
    limits=['Scope: registered observed window only; no complete request/token budget',
            'Interval sums overlap and are not request wall time or pure compute/transfer',
            'Missing CPU experts/Python stacks/scheduler activity remain unknown']
    if envelope['provenance']['provider']['name']=='http':
        metrics={}
        for case in {r.get('case') for r in rows}:
            selected=[r for r in rows if r.get('case')==case and not r.get('warmup')]
            metrics[str(case)]={'requests':len(selected),'http_wall_median_seconds':median(r['http_wall_seconds'] for r in selected) if selected else None,
                               'first_text_median_seconds':median(r['http_first_text_seconds'] for r in selected if r['http_first_text_seconds'] is not None) if any(r['http_first_text_seconds'] is not None for r in selected) else None}
        add('model','Recorded HTTP observations: '+str(metrics),{'case_metrics':metrics},base_evidence,
            ['First-text is not strict TTFT; SSE chunks are not token ITL','Reported decode speed is distinct from HTTP wall/service throughput','A single boot is not A/A or production P95'],
            'Compare complete independent trace-off boots under a matched contract and output/resource oracle')
    if measurement_ids:
        measured=[store.get('measurement',name) for name in measurement_ids]
        if any(m['body']['basis']!=basis for m in measured):raise ValueError('Model observation/measurement basis mismatch')
        registered_http={a['sha256'] for a in registered['artifacts'] if a['format']=='http'}
        primary={r['evidence'][0]['sha256'] for r in measured if r['evidence']}
        if primary!=registered_http or not primary:raise ValueError('Model measurement corpus differs from the registered HTTP inputs')
        target_aa=aa(settings,measurement_ids);contract=store.get('benchmark-contract',measured[0]['body']['contract_id'])['body']
        if contract['kind']!='model':raise ValueError('Model diagnosis requires model measurement records')
        if target_aa['passed']:
            for gate in target_aa['gates']:
                context=dict(measured[0]['body']['context'],case=gate['case'])
                target=median(gate['boot_medians'].values())
                for reference_id in references or []:
                    reference=store.get('reference',reference_id)['body'];match=reference_match(settings,reference_id,context)
                    if match['applicable'] and reference['kind']=='model' and reference['reference_type']=='same_condition_baseline' and reference['metric']==contract['metric']['name'] and reference['unit']==contract['metric']['unit']:
                        add('model',f'{gate["case"]}: qualified target boot median {target} versus reference {match["value"]} {match["unit"]}',
                            {'case':gate['case'],'metric':contract['metric'],'target_boot_median':target},
                            base_evidence+[{'measurements':target_aa['measurements']}],
                            ['Matched descriptive gap is not a causal optimization gain or a recoverable critical-path budget'],
                            'Use a preregistered paired trace-off candidate comparison to test the mechanism',target-match['value'],match)
        else:
            add('model','Independent model cohort remains inconclusive',{'aa':target_aa},base_evidence,
                ['No numeric model gap from an unstable/unqualified cohort'],'Resolve matching/output/resource/stability gates before attributing a gap')
    phases=defaultdict(list);inferred_phases=defaultdict(list)
    for row in rows:
        mapping=semantic.get(row.get('event_id'),{})
        if mapping.get('phase') is not None and mapping.get('association')=='exact':
            phases[(mapping.get('request'),mapping['phase'],mapping.get('token'),mapping.get('rank'))].append(row)
        elif mapping.get('phase') is not None and mapping.get('association')=='inferred':
            inferred_phases[(mapping.get('request'),mapping['phase'],mapping.get('token'),mapping.get('rank'))].append(row)
    dependency_projection={'status':'unknown','lower_bound_ns':None,'residual_ns':None}
    if map_record and map_record['body']['scope_complete']:
        mapping=map_record['body'];selected={r['event_id']:r for r in rows if r['event_id'] in semantic}
        domains={r['clock_domain'] for r in selected.values()}
        safe=bool(selected) and all(e['association']=='exact' for e in mapping['entries'])
        safe=safe and (len(domains)==1 or clock.get('calibrated') and set(clock.get('source_domains',[]))==domains and clock.get('domain'))
        parents=defaultdict(list)
        for edge in mapping['dependencies']:
            a,b=selected[edge['source']],selected[edge['target']]
            if int(a['start_ns'])+int(a['duration_ns'])>int(b['start_ns']):safe=False
            parents[edge['target']].append(edge['source'])
        if safe:
            memo={}
            def path_length(node):
                if node not in memo:memo[node]=int(selected[node]['duration_ns'])+max([path_length(p) for p in parents[node]] or [0])
                return memo[node]
            lower=max(path_length(node) for node in selected)
            envelope_ns=max(int(r['start_ns'])+int(r['duration_ns']) for r in selected.values())-min(int(r['start_ns']) for r in selected.values())
            dependency_projection={'status':'scoped_observed_lower_bound','lower_bound_ns':str(lower),'residual_ns':str(max(0,envelope_ns-lower)),
                'limit':'Observed non-overlapping dependency activities only; residual is unexplained, not idle or recoverable wall time'}
    add('model','Observed '+str(len(rows))+' records; exact semantic phase groups='+str(len(phases)),
        {'exact_groups':[list(k) for k in phases],'inferred_groups':[list(k) for k in inferred_phases],
         'dependency_projection':dependency_projection,'unmapped_records':sum(r.get('event_id') not in semantic for r in rows)},base_evidence,
        limits+['No numeric critical-path saving without a closed dependency scope and matched trace-off reference'],
        'Bind exact request/phase/token semantics for one bounded slow request; compare trace-off controls',
        alternatives=['Host preparation/CPU expert/offload/queue dependencies can be outside this ROI'])
    kernels=[r for r in rows if r.get('category') in ('kernel','kernel_dispatch')]
    groups=defaultdict(list)
    for row in kernels:groups[(row.get('rank'),row.get('name'),row.get('clock_domain'))].append(row)
    hottest=sorted(groups.items(),key=lambda item:sum(int(r['duration_ns']) for r in item[1]),reverse=True)[:12]
    if not hottest:
        add('kernel','Selected provider has no qualified kernel observations',{},base_evidence,
            ['Missing kernel records are unknown work, not zero GPU time'],'Collect/register a separately qualified native ROI if needed')
    for (rank,name,domain),instances in hottest:
        duration=sum(int(r['duration_ns']) for r in instances);representative=max(instances,key=lambda r:int(r['duration_ns']))
        mapping=semantic.get(representative['event_id'],{})
        context=mapping.get('kernel_context',{}) if mapping.get('association')=='exact' else {}
        match=None;gap=None
        for reference_id in references or []:
            candidate=reference_match(settings,reference_id,context)
            ref=store.get('reference',reference_id)['body']
            if candidate['applicable'] and ref['kind']=='kernel' and ref['metric']=='duration_ns' and ref['unit']=='ns':
                match=candidate;gap=int(representative['duration_ns'])-candidate['value'];break
        hint='collective_name_hint' if any(t in name.lower() for t in ('allreduce','all_reduce','nccl','rccl')) else 'copy_name_hint' if 'copy' in name.lower() else 'unclassified_kernel'
        add('kernel',f'{name}: {len(instances)} observed instances, interval sum {duration} ns; largest {representative["duration_ns"]} ns',
            {'rank':rank,'clock_domain':domain,'name_hint':hint,'event_id':representative['event_id'],'semantic':mapping},
            base_evidence+[{'event_id':representative['event_id'],'artifact_id':representative['artifact_id']}],
            ['Name hints do not prove a compute/bandwidth bottleneck','No shape/dtype/FLOP/byte estimate inferred from a kernel name',
             'Largest instance/reference delta is not recoverable model wall time'],
            'Replay the exact shape/layout on this device/runtime with a qualified timer and independent oracle',gap,match,
            ['Collective kernels can include readiness waits; copy kernels can carry traffic absent from memory_copy records'])
    rank_totals=defaultdict(lambda:{'kernels':0,'duration_sum_ns':0})
    for row in kernels:
        rank_totals[str(row.get('rank'))]['kernels']+=1;rank_totals[str(row.get('rank'))]['duration_sum_ns']+=int(row['duration_ns'])
    arrival_groups=defaultdict(list)
    for row in rows:
        meta=semantic.get(row.get('event_id'),{})
        keys=('request','phase','token','collective_sequence','process_group','op')
        if meta.get('association')=='exact' and meta.get('position_kind')=='collective_enter' and all(meta.get(k) is not None for k in keys):
            arrival_groups[tuple(object_hash(meta[k]) for k in keys)].append((row,meta))
    skews=[]
    world=registered['identity']['workload']['tp']
    for entries in arrival_groups.values():
        domains={r['clock_domain'] for r,_ in entries}
        if world and len(entries)==world and len({m.get('rank') for _,m in entries})==world and clock.get('calibrated') and set(clock.get('source_domains',[]))==domains and clock.get('domain'):
            times=[int(r['start_ns']) for r,_ in entries];spread=max(times)-min(times)
            uncertainty=clock.get('uncertainty_ns')
            if type(uncertainty) is int and uncertainty*2<spread:
                skews.append({'event_ids':[r['event_id'] for r,_ in entries],'entry_skew_ns':spread,'uncertainty_ns':uncertainty})
    add('multigpu','Per-rank observed kernel intervals: '+str(dict(rank_totals)),
        {'rank_totals':dict(rank_totals),'qualified_collective_entry_skews':skews},base_evidence,
        ['Same-name kernels do not establish same-request collective pairing','No pure transfer/rank-wait budget from dispatch intervals',
         'Entry skew is reported only for exact matched enter markers and qualified clocks; it is not pure wait time'],
        'Match collective sequence/payload/group at one request/token; use a controlled late-rank/payload counterfactual',
        alternatives=['Different logical work','Arrival skew','Topology/traffic path','Host scheduling or queue context'])
    case_body={'schema_version':1,'basis':basis,'status':'diagnostic','title':'Scoped model/kernel/multigpu diagnostic for '+run,
        'records':[{'kind':'finding','id':f['id'],'record_sha256':f['record_sha256']} for f in findings],
        'observation':str(len(findings))+' evidence-linked findings; unknown semantics/clocks remain explicit',
        'limits':limits,'reopen_when':'New matched trace-off controls or independently qualified semantic/clock/reference evidence'}
    case=store.add('case',output_prefix,case_body)
    Registry.verify(registered['artifacts'])
    return {'schema_version':1,'run_id':run,'case_id':case['id'],'case_sha256':case['record_sha256'],
            'findings':findings,'new_gpu_workload':False,'normal_speed_claim':False,'source_bytes_copied':0}

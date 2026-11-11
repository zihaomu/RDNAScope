"""Candidate-type-specific validation; analysis never modifies an accepted baseline."""
from .records import Records, evidence
from .benchmark import aa, compare

GATES={
 'kernel_layout':('independent_baseline','numeric_eager_graph','shape_layout_coverage','local_stability','local_effect'),
 'cache_transfer':('independent_baseline','output_reference','lifetime','subchain_correctness','local_stability'),
 'thread_config':('output_reference','resource_ownership'),
 'parallel_topology':('output_reference','model_semantics','rank_mapping','communication_correctness')}


def evaluate(settings,name,spec):
    candidate_type=spec.get('candidate_type')
    if candidate_type not in GATES:raise ValueError('Unknown candidate type')
    gates={};refs=[]
    required=list(GATES[candidate_type])
    if spec.get('math_changed'):required.append('full_numerical_protocol')
    for gate in required:
        ref=spec.get('gate_evidence',{}).get(gate)
        if ref is None:gates[gate]={'status':'not_run','reason':'No independently bound evidence'};continue
        if 'json_pointer' not in ref or type(ref.get('expected')) is not bool:
            raise ValueError('Gate evidence must be a typed boolean JSON assertion')
        evidence(settings,ref);refs.append(ref)
        gates[gate]={'status':'passed' if ref['expected'] else 'failed','evidence':ref}
    invalid=gates.get('independent_baseline',{}).get('status')=='failed'
    failures=[k for k,v in gates.items() if v['status']=='failed']
    missing=[k for k,v in gates.items() if v['status']=='not_run']
    aa_ids=spec.get('aa_measurements',[]);baseline=spec.get('baseline_measurements',[]);candidate=spec.get('candidate_measurements',[])
    store=Records(settings);binding_issues=[]
    for ids,side in [(aa_ids+baseline,'baseline'),(candidate,'candidate')]:
        for measurement_id in ids:
            m=store.get('measurement',measurement_id)['body']
            if m['context'].get('source_digest')!=spec[side].get('source_digest') or m['context'].get('source_digest') is None:
                binding_issues.append('source_binding:'+measurement_id)
            if m['basis']!=spec['basis']:binding_issues.append('basis_mismatch:'+measurement_id)
    aa_result=aa(settings,aa_ids) if aa_ids and not failures and not missing else None
    comparison=compare(settings,baseline,candidate) if baseline and candidate and aa_result and aa_result['passed'] else None
    decision='inconclusive';reason='required_evidence_missing_or_unqualified'
    if binding_issues:reason='measurement_candidate_binding_unqualified:'+','.join(binding_issues)
    elif invalid:reason='independent_fixture_control_invalid; not a candidate math rejection'
    elif any(k in failures for k in ('resource_ownership','rank_mapping')):
        reason='resource_or_rank_qualification_failed'
    elif any(k in failures for k in ('numeric_eager_graph','shape_layout_coverage','output_reference','lifetime','subchain_correctness','model_semantics','communication_correctness','full_numerical_protocol')):
        decision='rejected';reason='correctness_or_lifetime_gate_failed:'+','.join(failures)
    elif 'local_stability' in failures:reason='local_performance_not_identifiable'
    elif 'local_effect' in failures:decision='rejected';reason='qualified_local_effect_below_target'
    elif missing:reason='required_gate_not_run:'+','.join(missing)
    elif aa_result and not aa_result['passed']:reason='trace_off_AA_inconclusive'
    elif comparison:
        if comparison['status']=='rejected':decision='rejected';reason='matched_model_effect_below_preregistered_target'
        elif comparison['passed']:
            decision='validated' if comparison['classification']=='formal' else 'hypothesis'
            reason='formal_comparison_and_type_specific_gates_passed' if decision=='validated' else 'screening_passed; formal validation still required'
        else:reason='model_comparison_inconclusive'
    result={'schema_version':1,'basis':spec['basis'],'candidate_type':candidate_type,'hypothesis':spec['hypothesis'],
            'baseline':spec['baseline'],'candidate':spec['candidate'],
            'stages':{'gates':gates,'aa':aa_result or {'status':'not_run'},'model_comparison':comparison or {'status':'not_run'},'reason':reason},
            'decision':decision,'adopted':False,'source_action':'not_run' if spec.get('candidate_not_run') else 'rejected_isolated' if decision=='rejected' else 'preserved_isolated',
            'limits':['No accepted source was modified by evaluation','Skipped stages are not validation',
                      'Independent control failure differs from candidate correctness failure','Formal validated result is not automatic source adoption']}
    for measurement_id in set(aa_ids+baseline+candidate):
        # Bind exact immutable cohort records even when a gate stops later stages.
        record=store.get('measurement',measurement_id)
        result['stages'].setdefault('measurement_records',[]).append({'id':measurement_id,'record_sha256':record['record_sha256']})
    return store.add('experiment',name,result,refs)

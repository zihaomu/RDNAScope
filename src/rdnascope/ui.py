"""Read-only evidence location in the official Trace Processor/UI."""
import csv
import io

from .records import Records
from .storage import Registry,local_path,sqlite_readonly
from .providers import rocpd_specs,provider_info,bounded_process


def locate(settings,finding_id,pftrace_id=None,port=9001):
    store=Records(settings);store.verify_tree('finding',finding_id)
    finding=store.get('finding',finding_id)['body'];run=Registry(settings).inspect(finding['run_id'])
    event=finding['position'].get('event_id')
    if not event:raise ValueError('Choose a finding with a specific native event locator')
    artifact_id,locator=event.split('#',1)
    artifact=next(a for a in run['artifacts'] if a['artifact_id']==artifact_id)
    info=provider_info('pftrace',settings)
    if artifact['format']=='pftrace':
        old=next((e['provider'] for e in finding['evidence'] if e.get('provider',{}).get('name')=='pftrace'),None)
        if not old or old.get('binary_sha256')!=info['binary_sha256']:raise ValueError('Slice locator parser build differs; regenerate the finding')
        if not locator.startswith('slice/'):raise ValueError('Unsupported PFTrace locator')
        slice_id=int(locator.removeprefix('slice/'));selected=artifact
        sql='SELECT id,ts,dur,name FROM slice WHERE id='+str(slice_id)
    elif artifact['format']=='rocpd':
        if not pftrace_id:raise ValueError('Raw rocpd finding needs an explicit registered official PFTrace content ID')
        selected=next((a for a in run['artifacts'] if a['artifact_id']==pftrace_id and a['format']=='pftrace'),None)
        if not selected:raise ValueError('Selected PFTrace is not registered')
        table,native_id=locator.rsplit('/id=',1)
        with sqlite_readonly(local_path(artifact['uri'])) as c:
            spec=next((s for s in rocpd_specs(c) if s['table']==table),None)
            if spec is None:raise ValueError('Native table locator unavailable')
            row=c.execute('SELECT * FROM ('+spec['query']+') WHERE id=?',(int(native_id),)).fetchone()
        if not row:raise ValueError('Native event is absent')
        name="'"+row['name'].replace("'","''")+"'"
        pid='coalesce(p1.pid,p2.pid) IS NULL' if row['process_id'] is None else 'coalesce(p1.pid,p2.pid)='+str(int(row['process_id']))
        sql=("SELECT s.id,s.ts,s.dur,s.name FROM slice s LEFT JOIN thread_track tt ON s.track_id=tt.id "
             "LEFT JOIN thread th ON tt.utid=th.utid LEFT JOIN process p1 ON th.upid=p1.upid "
             "LEFT JOIN process_track pt ON s.track_id=pt.id LEFT JOIN process p2 ON pt.upid=p2.upid "
             "WHERE s.category='kernel_dispatch' AND s.name="+name+' AND s.ts='+str(row['start'])+
             ' AND s.dur='+str(row['end']-row['start'])+' AND '+pid)
    else:raise ValueError('Official native UI location currently supports raw rocpd/PFTrace findings')
    stdout,_=bounded_process([settings.trace_processor,'query','--no-agent','--format','csv',str(local_path(selected['uri'])),sql],settings.timeout_seconds)
    matches=list(csv.DictReader(io.StringIO(stdout)))
    if len(matches)!=1:raise ValueError('UI event location is absent or ambiguous; no invented slice mapping')
    Registry.verify(run['artifacts'])
    return {'schema_version':1,'finding_id':finding_id,'source_event_id':event,'selected_pftrace':selected['artifact_id'],
            'trace_processor':info,'slice':matches[0],'official_ui_sql':sql,
            'rpc_port':port,'ui_instruction':'Start/forward this selected PFTrace with service start; paste official_ui_sql in the official UI Query tab',
            'association':'unique observed name/time/PID match; native correlation IDs remain provider-scoped',
            'limits':['Location is not clock/model/performance qualification','No frontend or native trace serialization was added']}

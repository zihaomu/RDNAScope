"""Immutable portable records and locally bound, hash-checked evidence assertions."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from .core import canonical, file_hash, identifier, object_hash, read_json, validate

KINDS = ('capability','benchmark-contract','measurement','reference','finding','experiment','case','semantic-map')


def pointer(document, path):
    if path == '':return document
    if not isinstance(path,str) or not path.startswith('/'):
        raise ValueError('JSON pointer must be empty or begin with /')
    value=document
    for part in path[1:].split('/'):
        token=part.replace('~1','/').replace('~0','~')
        value=value[int(token)] if isinstance(value,list) else value[token]
    return value


def evidence(settings, reference):
    required={'source_id','relative_path','sha256'}
    if not isinstance(reference,dict) or not required<=set(reference) or set(reference)-required-{'json_pointer','expected','purpose'}:
        raise ValueError('Invalid evidence reference')
    source=identifier(reference['source_id'])
    roots=settings.source_roots
    if source not in roots:raise ValueError('Unbound evidence source: '+source)
    root=roots[source]
    relative=Path(reference['relative_path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Evidence must be source-relative without traversal')
    path=(root/relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():raise ValueError('Evidence escaped its bound source')
    if file_hash(path)!=reference['sha256']:raise ValueError('Evidence SHA mismatch: '+source+'/'+str(relative))
    if 'json_pointer' in reference:
        if 'expected' not in reference:raise ValueError('An assertion needs an expected typed value')
        actual=pointer(read_json(path,settings.max_json_bytes),reference['json_pointer'])
        if type(actual) is not type(reference['expected']) or actual!=reference['expected']:
            raise ValueError('Evidence JSON assertion failed')
    return {'source_id':source,'relative_path':str(relative),'sha256':reference['sha256'],'status':'verified'}


class Records:
    def __init__(self,settings):self.settings=settings;self.root=settings.data_dir/'records'

    def path(self,kind,name):
        if kind not in KINDS:raise ValueError('Unknown record kind')
        return self.root/kind/(identifier(name)+'.json')

    def add(self,kind,name,body,refs=None):
        validate(kind,body)
        refs=list({object_hash(ref):ref for ref in (refs or [])}.values())
        for ref in refs:evidence(self.settings,ref)
        from .lifecycle import CacheStore
        for ref in refs:
            if ref['source_id']=='rdnascope-cache':
                parts=Path(ref['relative_path']).parts
                if len(parts)>=2 and parts[0] in ('jobs','namespaces','queries'):
                    kind_prefix={'jobs':'job','namespaces':'namespace','queries':'query'}[parts[0]]
                    item=kind_prefix+':'+(Path(parts[1]).stem if kind_prefix=='query' else parts[1])
                    CacheStore(self.settings).reference(item,'record:'+kind+':'+name)
        envelope={'schema_version':1,'kind':kind,'id':identifier(name),'body':body,'evidence':refs,
                  'created_utc':datetime.now(timezone.utc).isoformat()}
        record=dict(envelope,record_sha256=object_hash(envelope))
        path=self.path(kind,name)
        if path.parent.is_symlink() or self.root.is_symlink():raise ValueError('Record storage must not be a symlink')
        path.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive create preserves rejected/failed attempts instead of overwriting.
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'w') as stream:
                stream.write(canonical(record)+'\n');stream.flush();os.fsync(stream.fileno())
        except BaseException:
            # An interrupted record stays present and fails integrity on read.
            raise
        return self.get(kind,name)

    def get(self,kind,name):
        path=self.path(kind,name)
        if path.is_symlink() or path.parent.is_symlink():raise ValueError('Record storage must not be a symlink')
        record=read_json(path,self.settings.max_json_bytes)
        body={k:v for k,v in record.items() if k!='record_sha256'}
        if record.get('schema_version')!=1 or record.get('kind')!=kind or record.get('id')!=name or object_hash(body)!=record.get('record_sha256'):
            raise ValueError('Immutable record integrity failure')
        validate(kind,record['body'])
        for ref in record['evidence']:evidence(self.settings,ref)
        return record

    def list(self,kind):
        if kind not in KINDS:raise ValueError('Unknown record kind')
        return [{'id':p.stem,'kind':kind,'record_sha256':self.get(kind,p.stem)['record_sha256']}
                for p in sorted((self.root/kind).glob('*.json'))]

    def verify_tree(self,kind,name,active=None):
        active=active or set();key=(kind,name)
        if key in active:raise ValueError('Case/reference record cycle')
        record=self.get(kind,name);children=[]
        if kind=='case':
            for ref in record['body']['records']:
                child=self.verify_tree(ref['kind'],ref['id'],active|{key})
                if child['record_sha256']!=ref['record_sha256']:raise ValueError('Case child record SHA mismatch')
                children.append(child)
        if kind=='experiment':
            for ref in record['body']['stages'].get('measurement_records',[]):
                child=self.verify_tree('measurement',ref['id'],active|{key})
                if child['record_sha256']!=ref['record_sha256']:raise ValueError('Experiment measurement SHA mismatch')
                children.append(child)
        if kind=='measurement':children.append(self.verify_tree('benchmark-contract',record['body']['contract_id'],active|{key}))
        if kind=='reference':
            for measurement in record['body']['measurement_ids']:children.append(self.verify_tree('measurement',measurement,active|{key}))
            if record['body']['capability_id']:children.append(self.verify_tree('capability',record['body']['capability_id'],active|{key}))
        if kind in ('finding','semantic-map'):
            from .storage import Registry
            registered=Registry(self.settings).inspect(record['body']['run_id'])
            available={a['artifact_id'] for a in registered['artifacts']}
            if kind=='finding':
                for ref in record['body']['evidence']:
                    if not set(ref.get('inputs',[]))<=available:raise ValueError('Finding input no longer registered')
                    if ref.get('semantic_map'):
                        child=self.verify_tree('semantic-map',ref['semantic_map']['id'],active|{key})
                        if child['record_sha256']!=ref['semantic_map']['record_sha256']:raise ValueError('Finding semantic map SHA mismatch')
                        children.append(child)
                    for m in ref.get('measurements',[]):
                        child=self.verify_tree('measurement',m['id'],active|{key})
                        if child['record_sha256']!=m['record_sha256']:raise ValueError('Finding measurement SHA mismatch')
                        children.append(child)
                reference=record['body'].get('reference')
                if reference:
                    child=self.verify_tree('reference',reference['reference_id'],active|{key})
                    if child['record_sha256']!=reference['record_sha256']:raise ValueError('Finding reference SHA mismatch')
                    children.append(child)
            elif not set(record['body']['input_artifacts'])<=available:raise ValueError('Semantic map input no longer registered')
            if kind=='semantic-map' and record['body']['clock'].get('capability_id'):
                children.append(self.verify_tree('capability',record['body']['clock']['capability_id'],active|{key}))
        return {'kind':kind,'id':name,'record_sha256':record['record_sha256'],'status':'verified','children':children}

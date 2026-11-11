"""Explicit, read-only AMD inventory. Discovery is not GPU qualification."""
import json
from pathlib import Path
import platform
import time

from .core import file_hash
from .providers import bounded_process


def discover(settings,requested=None):
    config=settings.machine
    smi=config.get('smi_executable')
    if not smi:raise ValueError('Explicit machine.smi_executable required for device discovery')
    smi=Path(smi).expanduser()
    if not smi.is_absolute():
        if not settings.config_path:raise ValueError('Relative SMI tool needs a profile')
        smi=(settings.config_path.parent/smi).resolve()
    out,_=bounded_process([str(smi),'--showproductname','--showbus','--showuniqueid','--json'],15)
    raw=json.loads(out);topology=Path(config.get('kfd_topology','/sys/class/kfd/kfd/topology/nodes'))
    process_root=Path(config.get('kfd_processes','/sys/class/kfd/kfd/proc'))
    proc_root=Path(config.get('proc_root','/proc'));nodes={};ordinal=0
    for p in sorted(topology.iterdir(),key=lambda p:int(p.name)):
        gpu=int((p/'gpu_id').read_text())
        if not gpu:continue
        props=dict(line.split(maxsplit=1) for line in (p/'properties').read_text().splitlines())
        loc=int(props['location_id']);pci=f'{int(props.get("domain",0)):04x}:{loc>>8:02x}:{(loc>>3)&31:02x}.{loc&7}'
        nodes[pci]={'kfd_node':int(p.name),'kfd_gpu_id':gpu,'hip_ordinal_unfiltered':ordinal};ordinal+=1
    devices=[]
    for card,info in raw.items():
        if not card.startswith('card'):continue
        pci=info['PCI Bus'].lower()
        if pci not in nodes:raise ValueError('SMI/PCI/KFD mapping incomplete')
        devices.append({'physical_smi':int(card[4:]),'pci':pci,'uuid':'GPU-'+info['Unique ID'][2:].zfill(16),
                        'model':info.get('Card Series'),'gfx':info.get('GFX Version'),**nodes[pci]})
    physical=requested if requested is not None else [d['physical_smi'] for d in devices]
    if len(physical)!=len(set(physical)):raise ValueError('Device selection contains duplicates')
    selected=[d for d in devices if d['physical_smi'] in physical]
    if len(selected)!=len(physical):raise ValueError('Requested device missing')
    processes=[];errors=[]
    for proc in process_root.iterdir():
        try:
            memory={str(d['physical_smi']):int((proc/f'vram_{d["kfd_gpu_id"]}').read_text()) for d in selected}
            if any(memory.values()):
                fields=(proc_root/proc.name/'stat').read_text().rsplit(')',1)[1].split()
                processes.append({'pid':int(proc.name),'start_ticks':fields[19],'vram_bytes':memory})
        except FileNotFoundError:continue
        except (OSError,ValueError) as exc:errors.append(str(exc))
    excluded=[d['physical_smi'] for d in selected if d['physical_smi'] in config.get('excluded_physical',[]) or d['hip_ordinal_unfiltered'] in config.get('excluded_unfiltered',[])]
    conflicts=[]
    reservation_dir=config.get('reservation_dir')
    if reservation_dir:
        for p in Path(reservation_dir).glob('gpu-reservation*.json'):
            try:
                record=json.loads(p.read_text())
                if record.get('status')=='active' and set(physical)&set(record.get('physical_gpus',[])):conflicts.append({'file':p.name,'owner':record.get('owner')})
            except (OSError,ValueError) as exc:errors.append(str(exc))
    available_ram=None;required_ram=config.get('min_available_ram_bytes')
    if required_ram is not None:
        if type(required_ram) is not int or required_ram<0:raise ValueError('RAM admission threshold must be nonnegative bytes')
        try:
            values=dict((line.split(':',1)[0],line.split(':',1)[1].strip()) for line in (proc_root/'meminfo').read_text().splitlines())
            available_ram=int(values['MemAvailable'].split()[0])*1024
            if available_ram<required_ram:errors.append('host_ram_below_profile_admission_threshold')
        except (OSError,KeyError,ValueError):errors.append('host_ram_observation_unavailable')
    return {'schema_version':1,'observed_monotonic_ns':time.monotonic_ns(),'kernel':platform.release(),
            'smi_sha256':file_hash(smi),'devices':devices,'selected':selected,'foreign_processes':processes,
            'errors':errors,'excluded_requested':excluded,'reservation_conflicts':conflicts,
            'available_ram_bytes':available_ram,'required_available_ram_bytes':required_ram,
            'status':'available_snapshot_only' if selected and not(processes or errors or excluded or conflicts) else 'resource_blocked',
            'scope':'Read-only snapshot; launch still requires a locked runtime lease and continuous ownership guard'}

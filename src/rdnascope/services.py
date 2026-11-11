"""Official Perfetto HTTP/RPC with upstream idle expiry and owned supervision."""
from pathlib import Path
import re
import socket
import time
from urllib.error import URLError
from urllib.request import urlopen

from .providers import bounded_process, provider_info
from .storage import Registry, local_path
from . import workers


def start(settings, run, artifact_id, port, idle_seconds=None, keep=False, max_rss_bytes=None, max_seconds=None):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('An explicit unprivileged localhost port is required')
    if keep == (idle_seconds is not None):
        raise ValueError('Choose positive idle seconds or explicit keep, exclusively')
    if idle_seconds is not None and (type(idle_seconds) is not int or idle_seconds <= 0):
        raise ValueError('Idle seconds must be positive')
    capture = Registry(settings).inspect(run)
    artifact = next((a for a in capture['artifacts'] if a['artifact_id'] == artifact_id and a['format'] == 'pftrace'), None)
    if not artifact:
        raise ValueError('Select a registered PFTrace content ID')
    info = provider_info('pftrace', settings)
    help_text, _ = bounded_process([settings.trace_processor, 'server', 'http', '--help'], 10)
    if '--idle-timeout' not in help_text or '--idle-start' not in help_text:
        raise ValueError('Configured official server lacks the required idle-timeout capability')
    match = re.search(r'Perfetto (v[0-9][A-Za-z0-9._-]*)', info['version'])
    if not match:
        raise ValueError('Cannot select an official UI version from this tool identity')
    # Refuse a port already in use; never stop or adopt its existing server.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))
    trace = local_path(artifact['uri'])
    argv = [settings.trace_processor, 'server', 'http', '--ip-address', '127.0.0.1',
            '--port', str(port), '--idle-timeout', 'never' if keep else str(idle_seconds) + 's', str(trace)]
    if not keep:
        argv[3:3]=['--idle-start', 'last-query']
    spec = {'kind': 'perfetto_http', 'argv': argv, 'tool': info,
            'trace': {'path': str(trace), 'sha256': artifact['sha256'], 'bytes': artifact['bytes'], 'artifact_id': artifact_id},
            'port': port, 'bind_address': '127.0.0.1', 'idle_seconds': idle_seconds, 'keep': keep,
            'idle_start': 'last-query' if not keep else None,
            'official_ui': f'https://ui.perfetto.dev/{match[1]}/#!/?rpc_port={port}',
            'reserve_bytes': 2 * 1024 * 1024, 'log_bytes': 1024 * 1024,
            'timeout_seconds': max_seconds, 'max_rss_bytes': max_rss_bytes}
    started = workers.start(settings, spec)
    deadline = time.monotonic() + 15
    try:
        while time.monotonic() < deadline:
            job = workers.status(settings, started['job'])
            if job['status'] not in ('queued', 'running'):
                raise ValueError('Official server exited before readiness; inspect ' + started['logs'])
            try:
                with urlopen(f'http://127.0.0.1:{port}/status', timeout=.3) as response:
                    if response.status == 200:
                        return dict(started, official_ui=spec['official_ui'], bind_address='127.0.0.1', port=port,
                                    idle_seconds=idle_seconds, ready=True, browser_rendered='not_tested',
                                    forwarding='Forward this RPC port in VS Code; open official_ui locally')
            except (URLError, OSError):
                pass
            time.sleep(.05)
        raise TimeoutError('Official RPC startup exceeded 15 seconds')
    except BaseException:
        workers.stop(settings, started['job'])
        workers.wait(settings, started['job'], 10)
        raise

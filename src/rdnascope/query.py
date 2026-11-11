"""Stable query envelopes and content-keyed derived-result reuse."""
from pathlib import Path
import platform
import sqlite3

from . import __version__
from .core import atomic_json, canonical, file_hash, object_hash, read_json, validate
from . import providers
from .storage import Registry
from .lifecycle import CacheStore

SUPPORTED = {
    'rocpd': {'summary', 'events', 'kernels'},
    'pftrace': {'summary', 'events', 'kernels'},
    'chrome': {'summary', 'events', 'kernels', 'phases'},
    'http': {'summary', 'metrics'},
    'legacy': {'summary', 'events', 'kernels', 'phases', 'collectives'},
}


def implementation_hash():
    resources = [Path(__file__), Path(providers.__file__), Path(__file__).with_name('core.py'),
                 Path(__file__).with_name('storage.py')]
    from .core import schema
    return object_hash({'package_version': __version__, 'python': platform.python_version(),
                        'sqlite': sqlite3.sqlite_version,
                        'schemas': {n: schema(n) for n in ('identity','artifact','query-result','quality')},
                        'files': {p.name: file_hash(p) for p in resources}})


def quality(identity, view_supported, rows, artifacts):
    refs = [a['artifact_id'] for a in artifacts]
    def check(status, reason):
        return {'status': status, 'reason': reason, 'evidence': refs}
    ranks = sorted(r['rank'] for r in identity['ranks'])
    tp = identity['workload']['tp']
    declared_coverage = 'unknown' if not ranks or tp is None else 'pass' if ranks == list(range(tp)) else 'fail'
    return validate('quality', {'schema_version': 1, 'capabilities': {
        'registered_bytes': check('pass', 'SHA verified before and after query/cache transfer; not full original collection qualification'),
        'query_view': check('pass' if view_supported else 'unknown', 'Provider supports the requested view' if view_supported else 'This provider has no qualified semantic implementation for this view; empty rows do not mean absence'),
        'observed_statistics': check('pass' if view_supported and rows else 'not_applicable', 'Observed returned records only; sums can overlap and do not represent request wall time'),
        'declared_rank_metadata': check(declared_coverage, 'Metadata coverage only; PID/rank association still requires independent workload proof'),
        'semantic_association': check('unknown', 'Explicit source fields and supplied mappings are retained; no complete adapter qualification in R1'),
        'graph_kernel_coverage': check('not_applicable' if identity['workload']['graph'] is False else 'unknown', 'No full Graph replay budget is inferred from observed events'),
        'cross_rank_clock': check('unknown', 'Shared host, supplied domain or timestamp preservation is not calibration proof'),
        'full_model_budget': check('unknown', 'ROI observations do not qualify all model phases/tokens'),
        'output_correctness': check('unknown', 'Reported HTTP parity is not an independent oracle audit'),
        'normal_performance': check('unknown', 'No new A/A, perturbation qualification or matched model A/B was executed')},
        'limits': ['No GPU job was launched by this command',
                   'CPU API/marker observations are not complete Python/CPU-expert or OS scheduler traces',
                   'Copy kernels/collectives may carry traffic even if memory_copy records are zero',
                   'Rows use native record ordering, not a reconstructed global critical path',
                   'R1 queries do not estimate calibrated rank wait, roofline or model speedup']})


def execute(settings, run, view='summary', provider='auto', limit=100, offset=0, cache=True, artifact_ids=None):
    if view not in providers.VIEWS or type(limit) is not int or not 1 <= limit <= 1000 or type(offset) is not int or offset < 0:
        raise ValueError('Unknown view or invalid page (limit 1..1000, offset >=0)')
    registry = Registry(settings)
    registered = registry.inspect(run)
    identity = registered['identity']
    candidates = registered['artifacts']
    if artifact_ids:
        unknown = set(artifact_ids) - {a['artifact_id'] for a in candidates}
        if unknown:
            raise ValueError('Requested artifact is not registered in this run')
        candidates = [a for a in candidates if a['artifact_id'] in artifact_ids]
    provider, artifacts = providers.select(candidates, provider)
    graph = {}
    for edge in registered['derivations']:
        graph.setdefault(edge['child'], set()).add(edge['parent'])
    def ancestors(node):
        result = {node}
        for parent in graph.get(node, ()):
            result |= ancestors(parent)
        return result
    for i, a in enumerate(artifacts):
        for b in artifacts[i + 1:]:
            if ancestors(a['artifact_id']) & ancestors(b['artifact_id']):
                raise ValueError('Related representations would double-count evidence; select explicit --artifact IDs')
    info = providers.provider_info(provider, settings)
    impl = implementation_hash()
    # Run names do not change source bytes/semantics and must not multiply caches.
    semantic_identity = {k: v for k, v in identity.items() if k not in ('run_id', 'experiment_id')}
    key = object_hash({'schema': 1, 'inputs': sorted(a['artifact_id'] for a in artifacts),
                       'identity': semantic_identity, 'provider': info, 'implementation': impl,
                       'view': view, 'limit': limit, 'offset': offset})
    path = settings.cache_dir / 'queries' / (key + '.json')
    if path.parent.is_symlink():
        raise ValueError('Managed query cache directory must not be a symlink')
    store = CacheStore(settings)
    if cache:
        with store.lease('query:' + key, 'query', reserve=0 if path.exists() else settings.query_reserve_bytes, writer=True) as token:
            return _page(settings, run, view, provider, limit, offset, cache, registered, identity,
                         artifacts, info, impl, semantic_identity, key, store, token)
    return _page(settings, run, view, provider, limit, offset, cache, registered, identity,
                 artifacts, info, impl, semantic_identity, key, store, None)


def _page(settings, run, view, provider, limit, offset, cache, registered, identity,
          artifacts, info, impl, semantic_identity, key, store, token):
    path = store.path('query:' + key)
    hit = False
    supported = view in SUPPORTED[provider] or view in ('coverage', 'provenance')
    if cache and path.exists():
        if path.is_symlink():
            raise ValueError('Derived cache object must not be a symlink')
        store.verify('query:' + key)
        saved = read_json(path, 8 * 1024 * 1024)
        if not isinstance(saved, dict) or saved.get('query_id') != key or object_hash(saved['payload']) != saved.get('payload_sha256'):
            raise ValueError('Derived cache object failed integrity check; original evidence was not modified')
        payload = saved['payload']; hit = True
    else:
        if view == 'provenance':
            rows = [{'artifact_id': a['artifact_id'], 'format': a['format'], 'bytes': a['bytes'],
                     'role': a['role'], 'storage': a['storage']} for a in artifacts][offset:offset + limit + 1]
        elif view == 'coverage':
            rows = [{'expected_tp': identity['workload']['tp'], 'declared_ranks': [r['rank'] for r in identity['ranks']],
                     'registered_inputs': len(artifacts), 'source_completeness': 'unknown',
                     'graph_coverage': 'unknown', 'cross_rank_clock': 'unknown'}][offset:offset + limit + 1]
        elif not supported:
            rows = []
        elif provider == 'rocpd':
            rows = providers.rocpd(artifacts, identity, view, settings, limit, offset)
        elif provider == 'pftrace':
            rows = providers.perfetto(artifacts, identity, view, settings, limit, offset)
        else:
            rows = providers.json_query(artifacts, identity, provider, view, settings, limit, offset)
        payload = {'rows': rows[:limit], 'has_more': len(rows) > limit}
        if len(canonical(payload).encode()) > 8 * 1024 * 1024 - 4096:
            raise ValueError('Query result exceeds byte budget; use a smaller page or summary')
    # Always verify all registered evidence, even for a cache hit or unused format.
    Registry.verify(registered['artifacts'])
    result = validate('query-result', {'schema_version': 1, 'run_id': run, 'query_id': key, 'view': view,
        'rows': payload['rows'], 'provenance': {'inputs': [a['artifact_id'] for a in artifacts],
            'provider': info, 'implementation': impl, 'identity_sha256': object_hash(semantic_identity)},
        'quality': quality(identity, supported, payload['rows'], artifacts),
        'page': {'limit': limit, 'offset': offset, 'returned': len(payload['rows']), 'has_more': payload['has_more']},
        'cache_hit': hit})
    if cache and not hit:
        store.publish_query(key, {'query_id': key, 'payload_sha256': object_hash(payload), 'payload': payload}, token)
    return result

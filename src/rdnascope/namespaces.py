"""Explicit ABI/codegen namespaces. No framework is imported or compiled here."""
import json
from .core import identifier, object_hash, validate
from .lifecycle import CacheStore

ENVIRONMENTS = {'triton': 'TRITON_CACHE_DIR', 'torchinductor': 'TORCHINDUCTOR_CACHE_DIR',
                'custom': 'RDNASCOPE_COMPILE_CACHE'}


def create(settings, fingerprint, cold_session=None):
    validate('cache-fingerprint', fingerprint)
    if cold_session is not None:
        identifier(cold_session)
    metadata = {'fingerprint': fingerprint, 'cold_session': cold_session,
                'protocol': 'rdnascope_exclusive_writer_v1'}
    item_id = 'namespace:' + object_hash(metadata)
    store = CacheStore(settings)
    with store.lease(item_id, 'namespace_create', writer=True):
        path = store.create_directory(item_id, metadata)
    return {'namespace': item_id, 'path': str(path), 'fingerprint_sha256': object_hash(fingerprint),
            'environment': {ENVIRONMENTS[fingerprint['backend']]: str(path / 'data')},
            'cache_condition': 'explicit_cold_session' if cold_session else 'shared_compatible_namespace',
            'use': 'cache run holds the exclusive writer lease; direct/uncoordinated writes are unsupported',
            'qualification': 'fingerprint declarations only; not a verified installed model/compiler environment'}


def check(store, item_id, fingerprint):
    validate('cache-fingerprint', fingerprint)
    if not item_id.startswith('namespace:'):
        raise ValueError('A managed namespace ID is required')
    with store.locked() as c:
        row = c.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
        if not row or row['status'] != 'ready':
            raise ValueError('Namespace is not available')
        metadata = json.loads(row['metadata'])
        if metadata['fingerprint'] != fingerprint:
            raise ValueError('Namespace ABI/codegen fingerprint mismatch; create another namespace')
    store.verify(item_id)
    return {ENVIRONMENTS[fingerprint['backend']]: str(store.path(item_id) / 'data')}

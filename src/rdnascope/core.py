"""Portable paths and strict, versioned data contracts. No GPU dependencies."""
import hashlib
from importlib.resources import files
import json
import math
import os
from pathlib import Path
import re
import tempfile
import tomllib

from jsonschema import Draft202012Validator

ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}"
SCHEMA_NAMES = ('identity', 'artifact', 'query-result', 'quality', 'cache-fingerprint',
                'capability','benchmark-contract','measurement','reference','finding','experiment','case','semantic-map')


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(ID_PATTERN, value):
        raise ValueError('ID must contain 1..128 letters, digits, underscores, dots or dashes')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def object_hash(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path, max_bytes=64 * 1024 * 1024):
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise ValueError('JSON exceeds input byte budget; select a smaller input or increase the configured limit')
    def invalid_constant(value):
        raise ValueError('Non-finite JSON number: ' + value)
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('Non-finite JSON number: ' + value)
        return number
    with path.open() as f:
        return json.load(f, parse_constant=invalid_constant, parse_float=finite_float)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(value) + '\n'
    name = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.rdnascope-', delete=False) as f:
            name = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def schema(name):
    if name not in SCHEMA_NAMES:
        raise ValueError('Unknown schema: ' + name)
    return json.loads(files('rdnascope').joinpath('schemas', 'v1', name + '.json').read_text())


def validate(name, value):
    errors = sorted(Draft202012Validator(schema(name)).iter_errors(value), key=lambda e: str(list(e.path)))
    if errors:
        e = errors[0]
        raise ValueError(f'{name} schema: /{"/".join(map(str, e.path))}: {e.message}')
    # JSON Schema does not reject IEEE infinities when called from Python.
    canonical(value)
    if name == 'identity':
        ranks = [r['rank'] for r in value['ranks']]
        pids = [r['process_id'] for r in value['ranks'] if r['process_id'] is not None]
        if len(set(ranks)) != len(ranks) or len(set(pids)) != len(pids):
            raise ValueError('Duplicate rank or process mapping')
    elif name == 'artifact' and value['artifact_id'] != 'sha256:' + value['sha256']:
        raise ValueError('Artifact ID must match its content SHA')
    elif name == 'query-result':
        validate('quality', value['quality'])
        if value['page']['returned'] != len(value['rows']) or len(value['rows']) > value['page']['limit']:
            raise ValueError('Query page count does not match returned rows/limit')
    return value


def minimal_identity(run, experiment=None):
    return validate('identity', {
        'schema_version': 1, 'experiment_id': identifier(experiment or run), 'run_id': identifier(run),
        'role': 'diagnostic', 'source': {'revision': None, 'patch_sha256': None},
        'environment': {'digest': None},
        'workload': {'name': None, 'model_revision': None, 'tp': None, 'ep': None, 'graph': None},
        'ranks': [], 'clock': {'domain': 'unknown', 'calibration': 'unknown', 'uncertainty_ns': None},
        'semantics': {'time_unit': 'us', 'native_rank': None}, 'extensions': {}})


class Settings:
    """CLI > environment > TOML > XDG. Relative TOML paths use its directory."""
    def __init__(self, config=None, data_dir=None, cache_dir=None):
        config = config or os.environ.get('RDNASCOPE_CONFIG')
        self.config_path = Path(config).expanduser().resolve() if config else None
        self.config = {}
        if self.config_path:
            with self.config_path.open('rb') as f:
                self.config = tomllib.load(f)
        for section in ('paths', 'tools', 'legacy', 'limits', 'storage', 'sources','adapters','machine'):
            if not isinstance(self.config.get(section, {}), dict):
                raise ValueError('Configuration section must be a table: ' + section)
        paths = self.config.get('paths', {})
        def configured(value):
            p = Path(value).expanduser()
            return (self.config_path.parent / p).resolve() if not p.is_absolute() else p.resolve()
        data_override = data_dir or os.environ.get('RDNASCOPE_DATA_DIR')
        self.data_dir = (Path(data_override).expanduser().resolve() if data_override else
                         configured(paths['data_dir']) if paths.get('data_dir') else
                         Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'rdnascope')
        cache_override = cache_dir or os.environ.get('RDNASCOPE_CACHE_DIR')
        self.cache_dir = (Path(cache_override).expanduser().resolve() if cache_override else
                          configured(paths['cache_dir']) if paths.get('cache_dir') else
                          self.data_dir / 'cache' if data_override or paths.get('data_dir') else
                          Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'rdnascope')
        if not self.data_dir.is_absolute() or not self.cache_dir.is_absolute():
            raise ValueError('XDG data/cache roots must be absolute paths')
        tool = self.config.get('tools', {}).get('trace_processor')
        legacy = self.config.get('legacy', {}).get('executable')
        self.trace_processor = str(configured(tool)) if tool else None
        self.legacy_executable = str(configured(legacy)) if legacy else None
        self.source_roots={identifier(k):configured(v) for k,v in self.config.get('sources',{}).items()}
        if 'rdnascope-cache' in self.source_roots and self.source_roots['rdnascope-cache']!=self.cache_dir:
            raise ValueError('rdnascope-cache is reserved for this configured cache root')
        self.source_roots['rdnascope-cache']=self.cache_dir
        if 'rdnascope-evidence' in self.source_roots and self.source_roots['rdnascope-evidence']!=self.data_dir/'evidence':
            raise ValueError('rdnascope-evidence is reserved for this configured evidence root')
        self.source_roots['rdnascope-evidence']=self.data_dir/'evidence'
        self.adapters=self.config.get('adapters',{})
        self.machine=self.config.get('machine',{})
        self.max_json_bytes = self.config.get('limits', {}).get('json_bytes', 64 * 1024 * 1024)
        self.timeout_seconds = self.config.get('limits', {}).get('query_seconds', 60)
        storage = self.config.get('storage', {})
        unknown = set(storage) - {'max_bytes', 'min_free_bytes', 'ttl_seconds', 'query_reserve_bytes'}
        if unknown:
            raise ValueError('Unknown storage policy field: ' + ', '.join(sorted(unknown)))
        self.storage_policy = {k: storage.get(k) for k in ('max_bytes', 'min_free_bytes', 'ttl_seconds')}
        self.query_reserve_bytes = storage.get('query_reserve_bytes', 8 * 1024 * 1024)
        for name, v in [*self.storage_policy.items(), ('query_reserve_bytes', self.query_reserve_bytes)]:
            if v is not None and (type(v) is not int or v < 0):
                raise ValueError('Storage ' + name + ' must be a nonnegative integer')
        if not self.query_reserve_bytes:
            raise ValueError('query_reserve_bytes must be positive')
        for name, v in [('json_bytes', self.max_json_bytes), ('query_seconds', self.timeout_seconds)]:
            if type(v) is not int or v <= 0:
                raise ValueError(name + ' must be a positive integer')


def ns(value, unit):
    if type(value) not in (int, float) or type(value) is float and not math.isfinite(value):
        raise ValueError('Invalid timestamp')
    if unit not in ('ns', 'us', 'ms', 's'):
        raise ValueError('Unknown timestamp unit')
    scaled = value * {'ns': 1, 'us': 1000, 'ms': 1000000, 's': 1000000000}[unit]
    if type(scaled) is float and not math.isfinite(scaled):
        raise ValueError('Timestamp conversion exceeds finite numeric range')
    return round(scaled)

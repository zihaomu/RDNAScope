"""Opt-in bridge to the untouched prototype CLI; never reinterpret old commands."""
import json
import os
from pathlib import Path
import subprocess
import sys

from .core import Settings


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    config = None
    if args[:1] == ['--config']:
        if len(args) < 2:
            print('tlp bridge: --config requires a TOML path', file=sys.stderr)
            return 2
        config, args = args[1], args[2:]
    try:
        settings = Settings(config)
        if not settings.legacy_executable:
            print('tlp is a compatibility bridge. Configure [legacy].executable in a TOML profile,\n'
                  'then use tlp --config PROFILE <original arguments>. New APIs use rdnascope.', file=sys.stderr)
            return 0 if args == ['--help'] else 2
        exe = Path(settings.legacy_executable)
        if os.environ.get('RDNASCOPE_LEGACY_DELEGATING') or exe.resolve() == Path(sys.argv[0]).resolve():
            raise ValueError('Refusing recursive legacy delegation')
        if not exe.is_file() or not os.access(exe, os.X_OK):
            raise ValueError('Configured legacy CLI is not executable')
        print('RDNAScope compatibility bridge: forwarding unchanged arguments to configured legacy CLI.', file=sys.stderr)
        return subprocess.run([str(exe), *args], env=dict(os.environ, RDNASCOPE_LEGACY_DELEGATING='1')).returncode
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'error', 'message': str(exc)}), file=sys.stderr)
        return 2

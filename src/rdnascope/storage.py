"""Local read-only file and sealed SQLite helpers."""
from pathlib import Path
import sqlite3
from urllib.parse import unquote, urlparse


def local_path(uri):
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        raise ValueError("Only local read-only evidence is supported")
    return Path(unquote(parsed.path))


def sqlite_readonly(path):
    source = Path(path)
    if source.is_symlink():
        raise ValueError("Native input must be a regular file")
    path = source.resolve(strict=True)
    if not path.is_file():
        raise ValueError("Native input must be a regular file")
    for suffix in ("-wal", "-journal"):
        side = Path(str(path) + suffix)
        if side.exists() and side.stat().st_size:
            raise ValueError("Unsealed SQLite input has an active WAL/journal")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection

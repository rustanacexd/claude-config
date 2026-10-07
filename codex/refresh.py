#!/usr/bin/env python3
import base64
import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import tomllib

MISSING = object()


def equal(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return type(a) is type(b) and a == b


def merge(previous, live, shared, path=(), conflicts=None):
    if equal(live, previous):
        return shared
    if isinstance(live, dict) and all(v is MISSING or isinstance(v, dict) for v in (previous, shared)):
        old = {} if previous is MISSING else previous
        new = {} if shared is MISSING else shared
        result = {}
        for key in sorted(old.keys() | live.keys() | new.keys()):
            value = merge(old.get(key, MISSING), live.get(key, MISSING), new.get(key, MISSING), path + (key,), conflicts)
            if value is not MISSING:
                result[key] = value
        return result
    if conflicts is not None and not equal(previous, shared) and not equal(live, shared):
        conflicts.append('.'.join(path))
    return live


def quote(value):
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def scalar(value):
    if isinstance(value, str):
        return quote(value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, list):
        return '[' + ', '.join(scalar(v) for v in value) + ']'
    if isinstance(value, dict):
        return '{' + ', '.join(quote(k) + ' = ' + scalar(v) for k, v in value.items()) + '}'
    raise TypeError(f'Unsupported TOML value type: {type(value).__name__}')


def render(config):
    lines = []
    def table(value, path):
        if path:
            lines.extend(['', '[' + '.'.join(quote(k) for k in path) + ']'])
        for key, item in value.items():
            if not isinstance(item, dict):
                lines.append(quote(key) + ' = ' + scalar(item))
        for key, item in value.items():
            if isinstance(item, dict):
                table(item, path + (key,))
    table(config, ())
    data = ('\n'.join(lines).lstrip('\n') + '\n').encode()
    if not equal(tomllib.loads(data.decode()), config):
        raise ValueError('TOML serialization changed the configuration')
    return data


def parse(data):
    return tomllib.loads(data.decode('utf-8'))


def read(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        if path.is_symlink():
            raise ValueError(f'Broken symlink: {path}')
        return None


def digest(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def atomic(path, data):
    if read(path) == data:
        os.chmod(path, 0o600)
        return
    temporary = path.with_name(path.name + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def correct_link(path, target):
    return path.is_symlink() and Path(os.path.abspath(path.parent / os.readlink(path))) == target


def install_link(path, target):
    if correct_link(path, target):
        return
    temporary = path.with_name(path.name + '.codex-link.tmp')
    if temporary.is_symlink():
        temporary.unlink()
    elif temporary.exists():
        raise ValueError(f'Unexpected link staging file: {temporary}')
    temporary.symlink_to(target)
    os.replace(temporary, path)
    sync_directory(path.parent)


def backup(home, replacements):
    existing = [(p, data) for p, data in replacements if data is not None or p.is_symlink()]
    if not existing:
        return
    root = home / 'backups'
    if root.is_symlink():
        raise ValueError(f'Unexpected backup-directory symlink: {root}')
    root.mkdir(mode=0o700, exist_ok=True)
    os.chmod(root, 0o700)
    folder = Path(tempfile.mkdtemp(prefix=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=root))
    for path, data in existing:
        if data is not None:
            atomic(folder / path.name, data)
        if path.is_symlink():
            atomic(folder / (path.name + '.symlink.json'), json.dumps({'target': os.readlink(path)}).encode() + b'\n')
    print(f'Codex originals backed up to {folder}')


def finish(repo, home, journal, transaction):
    config = repo / 'config.toml'
    snapshot = repo / '.template.snapshot.toml'
    destination = home / 'config.toml'
    observed = digest(read(destination))
    output = base64.b64decode(transaction['config'], validate=True)
    baseline = base64.b64decode(transaction['snapshot'], validate=True)
    parse(output)
    parse(baseline)
    if observed not in (transaction['before'], digest(output)):
        raise ValueError(f'Codex changed during interrupted refresh. Preserve {journal} and reconcile config.toml before retrying.')
    if digest(read(config)) not in (transaction['generated_before'], digest(output)):
        raise ValueError(f'Generated config changed during interrupted refresh. Preserve {journal} and reconcile before retrying.')
    agents = home / 'AGENTS.md'
    if not correct_link(agents, repo / 'AGENTS.md') and digest(read(agents)) != transaction['agents_before']:
        raise ValueError(f'Instructions changed during interrupted refresh. Preserve {journal} and reconcile AGENTS.md before retrying.')
    atomic(config, output)
    atomic(snapshot, baseline)
    install_link(destination, config)
    install_link(home / 'AGENTS.md', repo / 'AGENTS.md')
    journal.unlink()
    sync_directory(repo)


def refresh(repo, home):
    repo = repo.resolve()
    home = home.expanduser().absolute()
    template_bytes = (repo / 'config.template.toml').read_bytes()
    shared = parse(template_bytes)
    (repo / 'AGENTS.md').read_bytes()
    for name in ('config.toml', '.template.snapshot.toml', '.refresh.journal.json', '.refresh.lock', 'config.toml.tmp', '.template.snapshot.toml.tmp', '.refresh.journal.json.tmp'):
        if (repo / name).is_symlink():
            raise ValueError(f'Unexpected symlink in generated state: {repo / name}')
    live_path = home / 'config.toml'
    live_bytes = read(live_path)
    live = {} if live_bytes is None else parse(live_bytes)
    snapshot = repo / '.template.snapshot.toml'
    old_bytes = read(snapshot)
    previous = {} if old_bytes is None else parse(old_bytes)
    read(home / 'AGENTS.md')
    journal = repo / '.refresh.journal.json'
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_fd = os.open(repo / '.refresh.lock', os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'a') as lock:
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        live_bytes = read(live_path)
        live = {} if live_bytes is None else parse(live_bytes)
        old_bytes = read(snapshot)
        previous = {} if old_bytes is None else parse(old_bytes)
        if journal.exists():
            finish(repo, home, journal, json.loads(journal.read_text()))
            live_bytes = read(live_path)
            live = parse(live_bytes)
            previous = parse(snapshot.read_bytes())
        conflicts = []
        merged = merge(previous, live, shared, conflicts=conflicts)
        output = live_bytes if live_bytes is not None and equal(merged, live) else render(merged)
        agents_path = home / 'AGENTS.md'
        agents_bytes = read(agents_path)
        replacements = [(path, data) for path, data, target in ((live_path, live_bytes, repo / 'config.toml'), (agents_path, agents_bytes, repo / 'AGENTS.md')) if not correct_link(path, target)]
        if digest(read(live_path)) != digest(live_bytes):
            raise ValueError('Codex changed during refresh. Retry while Codex is idle.')
        backup(home, replacements)
        if digest(read(live_path)) != digest(live_bytes):
            raise ValueError('Codex changed during refresh. Retry while Codex is idle.')
        if digest(read(agents_path)) != digest(agents_bytes):
            raise ValueError('Instructions changed during refresh. Retry while instructions are idle.')
        transaction = {'agents_before': digest(agents_bytes), 'before': digest(live_bytes), 'generated_before': digest(read(repo / 'config.toml')), 'config': base64.b64encode(output).decode(), 'snapshot': base64.b64encode(template_bytes).decode()}
        atomic(journal, json.dumps(transaction).encode() + b'\n')
        finish(repo, home, journal, transaction)
        for key in conflicts:
            print(f'Codex local override retained: {key}')
        print('Codex configuration and instructions linked')


if __name__ == '__main__':
    try:
        refresh(Path(__file__).resolve().parent, Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f'Codex refresh failed: {error}', file=sys.stderr)
        sys.exit(1)

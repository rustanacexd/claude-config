import json
import os
from pathlib import Path
import tempfile

from .install import atomic, fingerprint, linked, locked, read, sync_parent


def config_link_target(home):
    marker = home / ".claude-config/config-link.json"
    if linked(marker):
        raise ValueError("Config link marker must not be linked")
    data = read(marker)
    if data is None:
        return None
    settings = json.loads(data)
    if not isinstance(settings, dict) or set(settings) != {"target"}:
        raise ValueError("Invalid config link marker")
    if not isinstance(settings["target"], str):
        raise ValueError("Invalid config link target")
    target = Path(settings["target"])
    path = home / "config.toml"
    if (
        not target.is_absolute()
        or linked(target.parent)
        or linked(target)
        or not target.is_file()
    ):
        raise ValueError("Config link target must be an existing regular file")
    if not path.is_symlink() or path.resolve() != target.resolve():
        raise ValueError("Codex config link changed; rerun manage.py link --app codex")
    return target


def link_codex_config(repo, home):
    import tomllib

    repo = repo.resolve()
    target = repo / "codex/config.toml"
    path = home / "config.toml"
    with locked(home) as state:
        if (state / "journal.json").exists():
            raise ValueError("Run refresh to recover the pending transaction before linking")
        if linked(target.parent) or linked(target):
            raise ValueError("Checkout config target must not be linked")
        if path.is_symlink() and path.resolve() != target:
            raise ValueError("Codex config already links to another checkout")
        original = read(path)
        if original is None:
            raise ValueError("Codex config is missing; run refresh before linking")
        tomllib.loads(original.decode())
        marker = state / "config-link.json"
        if linked(marker):
            raise ValueError("Config link marker must not be linked")
        if path.is_symlink():
            atomic(marker, json.dumps({"target": str(target)}).encode())
            return target
        before = fingerprint(path)
        target_before = read(target)
        fd, name = tempfile.mkstemp(prefix=".config-link-", dir=home)
        os.close(fd)
        temporary = Path(name)
        temporary.unlink()
        try:
            temporary.symlink_to(target)
            backups = state / "backups"
            if linked(backups):
                raise ValueError("Backup directory must not be linked")
            backups.mkdir(exist_ok=True)
            backup = Path(tempfile.mkdtemp(prefix="config-link-", dir=backups))
            atomic(backup / "config.toml", original)
            if target_before is not None:
                atomic(backup / "checkout-config.toml", target_before)
            if fingerprint(path) != before or read(target) != target_before:
                raise ValueError("Config changed while linking; retry while app is idle")
            atomic(target, original)
            atomic(marker, json.dumps({"target": str(target)}).encode())
            if fingerprint(path) != before:
                raise ValueError("Codex config changed while linking; retry while app is idle")
            os.replace(temporary, path)
            sync_parent(path)
        finally:
            temporary.unlink(missing_ok=True)
    return target

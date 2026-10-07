"""Owned files and recoverable app-home transactions."""

import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
from pathlib import PurePosixPath
import stat
import re


def read(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        if path.is_symlink():
            raise ValueError("Broken managed symlink")
        return None


def fingerprint(path):
    data = read(path)
    return {
        "hash": None if data is None else hashlib.sha256(data).hexdigest(),
        "link": os.readlink(path) if path.is_symlink() else None,
    }


def linked(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def safe_path(home, relative):
    if (
        not isinstance(relative, str)
        or not relative
        or ":" in relative
        or "\\" in relative
        or PurePosixPath(relative).is_absolute()
        or any(
            p in (".", "..")
            or p.endswith((" ", "."))
            or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?", p)
            for p in PurePosixPath(relative).parts
        )
        or PurePosixPath(relative).parts[0] == ".claude-config"
    ):
        raise ValueError("Unsafe managed destination")
    path = home / relative
    for parent in path.parents:
        if parent == home:
            break
        if linked(parent):
            raise ValueError("Managed destination has a symlink parent")
    return path


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".portable-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def locked(home):
    state = home / ".claude-config"
    if linked(state):
        raise ValueError("State directory must not be a symlink")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = state / "lock"
    if linked(lock):
        raise ValueError("Lock must not be a symlink")
    with lock.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield state
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def finish(home, state, transaction):
    if transaction.get("schema") != 1 or not isinstance(
        transaction.get("updates"), list
    ):
        raise ValueError("Unknown journal schema")
    # Verify every observation before any recovery write.
    for item in transaction["updates"]:
        path = safe_path(home, item["path"])
        data = (
            None
            if item["data"] is None
            else base64.b64decode(item["data"], validate=True)
        )
        after = {
            "hash": None if data is None else hashlib.sha256(data).hexdigest(),
            "link": None,
        }
        if fingerprint(path) not in (item["before"], after):
            raise ValueError(
                "App edited files during interrupted publication; preserve journal and reconcile before retrying"
            )
    for item in transaction["updates"]:
        path = safe_path(home, item["path"])
        if item["data"] is None:
            if path.exists() or path.is_symlink():
                path.unlink()
        else:
            data = base64.b64decode(item["data"])
            if read(path) != data or path.is_symlink():
                atomic(path, data)
    atomic(
        state / "baseline.json",
        json.dumps(transaction["baseline"], sort_keys=True).encode(),
    )
    (state / "journal.json").unlink()


def recover(home, state):
    journal = state / "journal.json"
    if linked(journal):
        raise ValueError("Journal must not be a symlink")
    if journal.exists():
        finish(home, state, json.loads(journal.read_text()))


def publish(home, state, updates, baseline):
    if (
        not updates
        and read(state / "baseline.json")
        == json.dumps(baseline, sort_keys=True).encode()
    ):
        return
    records = []
    backup = None
    for relative, (_, before) in updates.items():
        if fingerprint(safe_path(home, relative)) != before:
            raise ValueError(
                "App edited file before publication; retry while app is idle"
            )
    for relative, update in updates.items():
        data, before = update
        path = safe_path(home, relative)
        if fingerprint(path) != before:
            raise ValueError(
                "App edited file before publication; retry while app is idle"
            )
        if before["hash"] is not None or before["link"] is not None:
            if backup is None:
                root = state / "backups"
                if linked(root):
                    raise ValueError("Backup directory must not be linked")
                root.mkdir(exist_ok=True)
                backup = Path(tempfile.mkdtemp(dir=root))
            old = read(path)
            if old is not None:
                atomic(backup / relative, old)
            if before["link"]:
                atomic(
                    backup / (relative + ".symlink.json"),
                    json.dumps({"target": before["link"]}).encode(),
                )
        records.append(
            {
                "path": relative,
                "before": before,
                "data": None if data is None else base64.b64encode(data).decode(),
            }
        )
    transaction = {"schema": 1, "updates": records, "baseline": baseline}
    atomic(state / "journal.json", json.dumps(transaction).encode())
    finish(home, state, transaction)

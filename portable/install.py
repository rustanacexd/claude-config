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


def sync_parent(path):
    if os.name != "nt":
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def root_for(relative, roots):
    return next((r for r in roots if relative.startswith(r["path"] + "/")), None)


def validate_transaction(home, transaction, repo=None, manifest=None, app=None):
    if not isinstance(transaction, dict):
        raise ValueError("Invalid journal")
    if transaction.get("schema") != 1 or not isinstance(
        transaction.get("updates"), list
    ):
        raise ValueError("Unknown journal schema")
    baseline = transaction.get("baseline")
    if (
        not isinstance(baseline, dict)
        or baseline.get("schema") != 1
        or not isinstance(baseline.get("files"), dict)
        or not isinstance(baseline.get("config"), dict)
    ):
        raise ValueError("Invalid journal baseline")
    for name, digest in baseline["files"].items():
        safe_path(Path("/virtual"), name)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid journal baseline hash")
    roots = transaction.get("roots", [])
    if not isinstance(roots, list):
        raise ValueError("Invalid directory conversion journal")
    if roots and (repo is None or manifest is None or app is None):
        raise ValueError("Directory recovery requires manifest context")
    names = []
    for root in roots:
        if not isinstance(root, dict) or not all(
            isinstance(root.get(key), str) for key in ("path", "source", "link")
        ):
            raise ValueError("Invalid conversion root")
        if not isinstance(root.get("directories", []), list) or not all(
            isinstance(d, str) for d in root.get("directories", [])
        ):
            raise ValueError("Invalid conversion directories")
        name = root["path"]
        path = safe_path(home, name)
        if repo is not None:
            if not any(
                a["destination"] == name
                and a["source"] == root["source"]
                and app in a["apps"]
                and (repo / a["source"]).is_dir()
                for a in manifest["assets"]
            ):
                raise ValueError("Directory conversion no longer matches manifest")
            source = repo / root["source"]
            expected_directories = {
                name + "/" + d.relative_to(source).as_posix()
                for d in source.rglob("*")
                if d.is_dir()
            }
            if set(root.get("directories", [])) != expected_directories:
                raise ValueError("Conversion directories no longer match manifest")
            target = Path(root["link"])
            if not target.is_absolute():
                target = path.parent / target
            if not target.is_dir() or not os.path.samefile(target, source):
                raise ValueError("Directory conversion has foreign source")
        if any(
            name == n or name.startswith(n + "/") or n.startswith(name + "/")
            for n in names
        ):
            raise ValueError("Overlapping directory conversions")
        names.append(name)
        for directory in root.get("directories", []):
            safe_path(Path("/virtual"), directory)
            if not directory.startswith(name + "/"):
                raise ValueError("Invalid conversion directory")
        if linked(path):
            if (
                not path.is_symlink()
                or str(path.readlink()) != root["link"]
                or not path.is_dir()
            ):
                raise ValueError("App changed directory during interrupted publication")
        elif path.exists() and not path.is_dir():
            raise ValueError("App changed directory during interrupted publication")
    decoded = {}
    for item in transaction["updates"]:
        if not isinstance(item, dict) or not {"path", "before", "data"} <= item.keys():
            raise ValueError("Invalid journal update")
        if not isinstance(item["path"], str) or (
            item["data"] is not None and not isinstance(item["data"], str)
        ):
            raise ValueError("Invalid journal update")
        name = item["path"]
        root = root_for(name, roots)
        path = home / name if root else safe_path(home, name)
        safe_path(Path("/virtual"), name)
        if root and repo is not None:
            source_file = repo / root["source"] / name[len(root["path"]) + 1 :]
            if (
                not source_file.is_file()
                or source_file.is_symlink()
                or item["data"] is None
            ):
                raise ValueError("Conversion update no longer matches manifest")
        if name in decoded or name in names:
            raise ValueError("Duplicate journal destination")
        data = (
            None
            if item["data"] is None
            else base64.b64decode(item["data"], validate=True)
        )
        before = item["before"]
        if not isinstance(before, dict) or set(before) != {"hash", "link"}:
            raise ValueError("Invalid journal fingerprint")
        if (
            before["hash"] is not None
            and (
                not isinstance(before["hash"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", before["hash"])
            )
        ) or (before["link"] is not None and not isinstance(before["link"], str)):
            raise ValueError("Invalid journal fingerprint")
        after = {
            "hash": None if data is None else hashlib.sha256(data).hexdigest(),
            "link": None,
        }
        if root and (home / root["path"]).is_symlink():
            current = {"hash": None, "link": None}
        else:
            safe_path(home, name)
            current = fingerprint(path)
        if current not in (before, after) or (
            root and before != {"hash": None, "link": None}
        ):
            raise ValueError(
                "App edited files during interrupted publication; preserve journal and reconcile before retrying"
            )
        decoded[name] = data
    for root in roots:
        if repo is not None:
            source = repo / root["source"]
            expected_files = {
                root["path"] + "/" + p.relative_to(source).as_posix()
                for p in source.rglob("*")
                if p.is_file()
            }
            if {name for name in decoded if root_for(name, [root])} != expected_files:
                raise ValueError("Conversion files no longer match manifest")
        path = home / root["path"]
        if path.is_symlink() or not path.exists():
            continue
        directories = set(root.get("directories", []))
        directories.update(
            str(PurePosixPath(n).parent) for n in decoded if root_for(n, [root])
        )
        directories.update(
            str(p)
            for n in list(directories)
            for p in PurePosixPath(n).parents
            if str(p).startswith(root["path"] + "/")
        )
        for entry in path.rglob("*"):
            name = entry.relative_to(home).as_posix()
            if (
                linked(entry)
                or (entry.is_dir() and name not in directories)
                or (
                    not entry.is_dir()
                    and (name not in decoded or decoded[name] != read(entry))
                )
            ):
                raise ValueError("App edited directory during interrupted publication")
    return decoded


def finish(home, state, transaction, repo=None, manifest=None, app=None):
    decoded = validate_transaction(home, transaction, repo, manifest, app)
    for root in transaction.get("roots", []):
        path = home / root["path"]
        if path.is_symlink():
            if os.name == "nt":
                path.rmdir()
            else:
                path.unlink()
            sync_parent(path)
        path.mkdir(parents=True, exist_ok=True)
        sync_parent(path)
        for name in root.get("directories", []):
            directory = safe_path(home, name)
            directory.mkdir(parents=True, exist_ok=True)
            sync_parent(directory)
    for name, data in decoded.items():
        path = safe_path(home, name)
        if data is None:
            if path.exists() or path.is_symlink():
                path.unlink()
        elif read(path) != data or path.is_symlink():
            atomic(path, data)
    atomic(
        state / "baseline.json",
        json.dumps(transaction["baseline"], sort_keys=True).encode(),
    )
    (state / "journal.json").unlink()


def validate_journal(home, state, repo=None, manifest=None, app=None):
    if linked(state):
        raise ValueError("State directory must not be a symlink")
    journal = state / "journal.json"
    if linked(journal):
        raise ValueError("Journal must not be a symlink")
    if journal.exists():
        validate_transaction(home, json.loads(journal.read_text()), repo, manifest, app)
        return True
    return False


def recover(home, state, repo=None, manifest=None, app=None):
    if validate_journal(home, state, repo, manifest, app):
        finish(
            home,
            state,
            json.loads((state / "journal.json").read_text()),
            repo,
            manifest,
            app,
        )


def publish(
    home, state, updates, baseline, roots=None, repo=None, manifest=None, app=None
):
    roots = [] if roots is None else roots
    if (
        not updates
        and not roots
        and read(state / "baseline.json")
        == json.dumps(baseline, sort_keys=True).encode()
    ):
        return
    for root in roots:
        path = safe_path(home, root["path"])
        if not path.is_symlink() or str(path.readlink()) != root["link"]:
            raise ValueError("App changed directory before publication")
    records = [
        {
            "path": name,
            "before": before,
            "data": None if data is None else base64.b64encode(data).decode(),
        }
        for name, (data, before) in updates.items()
    ]
    transaction = {"schema": 1, "updates": records, "baseline": baseline}
    if roots:
        transaction["roots"] = roots
    backup = None
    for relative, (data, before) in updates.items():
        if root_for(relative, roots):
            continue
        path = safe_path(home, relative)
        if fingerprint(path) != before:
            raise ValueError(
                "App edited file before publication; retry while app is idle"
            )
    validate_transaction(home, transaction, repo, manifest, app)
    for relative, (data, before) in updates.items():
        if before["hash"] is None and before["link"] is None:
            continue
        path = safe_path(home, relative)
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
    if roots:
        root = state / "backups"
        if linked(root):
            raise ValueError("Backup directory must not be linked")
        root.mkdir(exist_ok=True)
        backup = backup or Path(tempfile.mkdtemp(dir=root))
        for conversion in roots:
            atomic(
                backup / (conversion["path"] + ".symlink.json"),
                json.dumps({"target": conversion["link"]}).encode(),
            )
    atomic(state / "journal.json", json.dumps(transaction).encode())
    finish(home, state, transaction, repo, manifest, app)

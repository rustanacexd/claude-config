import hashlib
import json
from pathlib import PurePosixPath
import re
import sys
import tomllib
from .config import merge, equal, render
from .install import read, safe_path, locked, recover, publish, fingerprint


def relative(value):
    if not isinstance(value, str) or "\\" in value or ":" in value:
        raise ValueError("Invalid manifest path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(
        p in ("..", ".")
        or p.endswith((" ", "."))
        or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?", p)
        for p in path.parts
    ):
        raise ValueError("Unsafe manifest path")
    return value


def load(repo):
    manifest = json.loads((repo / "portable.json").read_text())
    plugins = json.loads((repo / "plugins.json").read_text())
    if manifest.get("schema") != 1 or plugins.get("schema") != 1:
        raise ValueError("Unsupported manifest schema")
    seen = set()
    for asset in manifest["assets"]:
        relative(asset["source"])
        relative(asset["destination"])
        source = repo / asset["source"]
        if not source.exists() or source.is_symlink():
            raise ValueError("Missing or linked manifest source")
        for path in [source] if source.is_file() else source.rglob("*"):
            if path.is_symlink():
                raise ValueError("Linked source asset")
            if path.is_file():
                relative(path.relative_to(repo).as_posix())
                dest = asset["destination"] + (
                    ""
                    if source.is_file()
                    else "/" + path.relative_to(source).as_posix()
                )
                for app in asset["apps"]:
                    if app not in ("claude", "codex") or (app, dest.casefold()) in seen:
                        raise ValueError("Duplicate or invalid app destination")
                    seen.add((app, dest.casefold()))
    ids = set()
    for p in plugins["plugins"]:
        if (
            p["app"] not in ("claude", "codex")
            or not isinstance(p["enabled"], bool)
            or p["kind"] not in ("native", "account", "app-provided")
            or not re.fullmatch(r"[\w.-]+@[\w.-]+", p["id"])
        ):
            raise ValueError("Invalid plugin declaration")
        if (p["app"], p["id"]) in ids:
            raise ValueError("Duplicate plugin")
        ids.add((p["app"], p["id"]))
        if p["kind"] == "native" and (
            not isinstance(p["source"], str)
            or not p["source"].startswith("https://github.com/")
            or "@" in p["source"]
        ):
            raise ValueError("Invalid marketplace source")
    return manifest, plugins["plugins"]


def validate_shared(config):
    secret_names = {
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "EXA_API_KEY",
        "SENTRY_ACCESS_TOKEN",
        "ANTHROPIC_BASE_URL",
    }

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.upper() in secret_names or key.lower() in {
                    "api_key",
                    "access_token",
                    "auth_token",
                    "password",
                }:
                    raise ValueError(
                        "Shared template contains machine authentication; move it to the local profile"
                    )
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and (
            "/Users/" in value or re.search(r"https?://[^/\s]+@", value)
        ):
            raise ValueError(
                "Shared template contains machine paths or URL credentials"
            )

    walk(config)


def desired(repo, manifest, plugins, app, home):
    files = {}
    for asset in manifest["assets"]:
        if app not in asset["apps"]:
            continue
        source = repo / asset["source"]
        for path in [source] if source.is_file() else source.rglob("*"):
            if path.is_file():
                dest = asset["destination"] + (
                    ""
                    if source.is_file()
                    else "/" + path.relative_to(source).as_posix()
                )
                files[dest] = path.read_bytes()
    if app == "claude":
        shared = json.loads((repo / "settings.json").read_text())
        name = "settings.json"
        validate_shared(shared)
        shared["enabledPlugins"] = {
            p["id"]: p["enabled"] for p in plugins if p["app"] == app
        }
        shared["statusLine"] = {
            "type": "command",
            "command": f'"{sys.executable}" "{home / "statusline.py"}"',
        }
    else:
        shared = tomllib.loads((repo / "codex/config.template.toml").read_text())
        name = "config.toml"
        validate_shared(shared)
        shared["plugins"] = {
            p["id"]: {"enabled": p["enabled"]} for p in plugins if p["app"] == app
        }
        shared.setdefault("mcp_servers", {}).setdefault(
            "sentry",
            {
                "command": sys.executable,
                "args": [str(home / "sentry_mcp.py")],
                "env_vars": [
                    "SENTRY_ACCESS_TOKEN",
                    "APPDATA",
                    "LOCALAPPDATA",
                    "USERPROFILE",
                    "SYSTEMROOT",
                    "TEMP",
                    "TMP",
                ],
            },
        )
    profile = read(home / "portable.local.json")
    if profile is not None:
        local = json.loads(profile)
        if not isinstance(local, dict):
            raise ValueError("Local profile must be an object")
        shared = merge({}, local, shared)
    return files, name, shared


def parse(app, data):
    result = json.loads(data) if app == "claude" else tomllib.loads(data.decode())
    if not isinstance(result, dict):
        raise ValueError("Config must be an object")
    return result


def plan(repo, manifest, plugins, app, home, state):
    files, name, shared = desired(repo, manifest, plugins, app, home)
    if (state / "baseline.json").is_symlink():
        raise ValueError("Baseline must not be a symlink")
    baseline_bytes = read(state / "baseline.json")
    baseline = (
        {"schema": 1, "files": {}, "config": {}}
        if baseline_bytes is None
        else json.loads(baseline_bytes)
    )
    if baseline.get("schema") != 1:
        raise ValueError("Unsupported baseline schema")
    old = baseline["config"]
    live_bytes = read(safe_path(home, name))
    live = {} if live_bytes is None else parse(app, live_bytes)
    if (
        baseline_bytes is None
        and app == "codex"
        and (home / name).is_symlink()
        and (home / name).resolve() == (repo / "codex/config.toml").resolve()
    ):
        snapshot = read(repo / "codex/.template.snapshot.toml")
        if snapshot is not None:
            old = parse(app, snapshot)
    merged = merge(old, live, shared)
    output = (
        live_bytes
        if live_bytes is not None and equal(live, merged)
        else (
            json.dumps(merged, indent=2).encode() + b"\n"
            if app == "claude"
            else render(merged)
        )
    )
    updates = {}
    owned = {}
    issues = []
    for dest, data in files.items():
        path = safe_path(home, dest)
        current = read(path)
        current_hash = None if current is None else hashlib.sha256(current).hexdigest()
        new_hash = hashlib.sha256(data).hexdigest()
        previous = baseline["files"].get(dest)
        if current == data:
            owned[dest] = new_hash
            if path.is_symlink():
                updates[dest] = data
        elif current is None and previous is not None:
            owned[dest] = previous
            issues.append(f"{app}: local deletion retained: {dest}")
        elif (
            current is None
            or current_hash == previous
            or (
                previous is None
                and path.is_symlink()
                and path.resolve() == (repo / dest).resolve()
            )
        ):
            updates[dest] = data
            owned[dest] = new_hash
        else:
            if previous is not None:
                owned[dest] = previous
            issues.append(f"{app}: local file retained: {dest}")
    for dest, previous in baseline["files"].items():
        relative(dest)
        if dest not in files:
            path = safe_path(home, dest)
            current = read(path)
            if current is not None and hashlib.sha256(current).hexdigest() == previous:
                updates[dest] = None
            elif current is not None:
                owned[dest] = previous
                issues.append(f"{app}: edited removed asset retained: {dest}")
    if output != live_bytes or (home / name).is_symlink():
        updates[name] = output
    for dest in files:
        path = safe_path(home, dest)
        if path.is_symlink() and dest not in updates:
            updates[dest] = read(path)
    updates = {
        dest: (data, fingerprint(safe_path(home, dest)))
        for dest, data in updates.items()
    }
    return updates, {"schema": 1, "files": owned, "config": shared}, issues


def refresh(repo, homes, apps):
    manifest, plugins = load(repo)
    if (repo / "codex/.refresh.journal.json").exists():
        raise ValueError(
            "Legacy Codex journal must be recovered using the old refresh version before migration"
        )
    for app in apps:
        plan(repo, manifest, plugins, app, homes[app], homes[app] / ".claude-config")
    changed = []
    issues = []
    for app in apps:
        home = homes[app]
        with locked(home) as state:
            recover(home, state)
            updates, baseline, retained = plan(
                repo, manifest, plugins, app, home, state
            )
            publish(home, state, updates, baseline)
            changed.extend(f"{app}: {p}" for p in updates)
            issues.extend(retained)
    return changed, issues

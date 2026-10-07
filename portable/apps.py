"""Native app plugin managers. Their caches and login stores stay native."""

import json
import os
from pathlib import Path
import shutil
import subprocess


def command(app, arguments, home, parse_json=True, missing_message=None):
    executable = shutil.which(app)
    if not executable:
        raise ValueError(
            f"{app} CLI missing; install it, or use bootstrap --install-tools"
        )
    argv = [executable, *arguments]
    if os.name == "nt" and Path(executable).suffix.lower() in (".cmd", ".bat"):
        argv = [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/s",
            "/c",
            subprocess.list2cmdline(argv),
        ]
    env = dict(os.environ)
    env["CODEX_HOME" if app == "codex" else "CLAUDE_CONFIG_DIR"] = str(home)
    result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=180)
    if result.returncode:
        if (
            result.returncode == 1
            and missing_message
            and result.stderr.startswith(missing_message)
        ):
            return None
        raise ValueError(f"{app} native command failed: {arguments[0]} {arguments[1]}")
    if not parse_json:
        return result.stdout
    try:
        return json.loads(result.stdout) if result.stdout.strip() else None
    except json.JSONDecodeError:
        raise ValueError(f"{app} returned invalid JSON") from None


def installed(app, home):
    result = command(app, ["plugin", "list", "--json"], home)
    rows = (
        result
        if isinstance(result, list)
        else result.get("installed", [])
        if isinstance(result, dict)
        else None
    )
    if not isinstance(rows, list):
        raise ValueError(f"{app} returned unexpected plugin list")
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{app} returned unexpected plugin record")
        identifier = row.get("id", row.get("pluginId"))
        if not isinstance(identifier, str):
            raise ValueError(f"{app} returned missing plugin identifier")
        found[identifier] = row
    return found


def restore(app, home, plugins):
    issues = []
    try:
        found = installed(app, home)
        marketplaces = command(app, ["plugin", "marketplace", "list", "--json"], home)
        rows = (
            marketplaces
            if isinstance(marketplaces, list)
            else marketplaces.get("marketplaces", [])
            if isinstance(marketplaces, dict)
            else []
        )
        known = {
            x.get("name", x.get("marketplaceName")) for x in rows if isinstance(x, dict)
        }
        for plugin in plugins:
            identifier = plugin["id"]
            if identifier not in found:
                if plugin["kind"] != "native":
                    issues.append(
                        f"{app}: {identifier} requires "
                        + (
                            "app availability"
                            if plugin["kind"] == "app-provided"
                            else "account connection"
                        )
                    )
                    continue
                if plugin["marketplace"] not in known:
                    args = ["plugin", "marketplace", "add", plugin["source"]]
                    args += (
                        ["--scope", "user", "--json"] if app == "claude" else ["--json"]
                    )
                    command(app, args, home)
                    known.add(plugin["marketplace"])
                args = ["plugin", "install" if app == "claude" else "add", identifier]
                args += ["--scope", "user", "--json"] if app == "claude" else ["--json"]
                command(app, args, home)
                found = installed(app, home)
                if identifier not in found:
                    raise ValueError(f"{app} did not install {identifier}")
            if (
                app == "claude"
                and not plugin["enabled"]
                and found[identifier].get("enabled", True)
            ):
                command(
                    app,
                    ["plugin", "disable", identifier, "--scope", "user"],
                    home,
                    parse_json=False,
                )
        found = installed(app, home)
        for plugin in plugins:
            if (
                plugin["id"] in found
                and found[plugin["id"]].get("enabled") != plugin["enabled"]
            ):
                issues.append(
                    f"{app}: plugin enablement differs for {plugin['id']}; local setting retained"
                )
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        issues.append(str(error))
    return issues


def install_tools(apps):
    for app in apps:
        if shutil.which(app):
            continue
        if os.name == "nt" and shutil.which("winget"):
            package = "Anthropic.ClaudeCode" if app == "claude" else "OpenAI.Codex"
            args = [
                "winget",
                "install",
                "--id",
                package,
                "--exact",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        elif shutil.which("npm"):
            args = [
                "npm",
                "install",
                "-g",
                "@anthropic-ai/claude-code" if app == "claude" else "@openai/codex",
            ]
        else:
            raise ValueError(
                f"Cannot install {app}: install Node/npm or Windows winget, then retry --install-tools"
            )
        if subprocess.run(args, check=False).returncode:
            raise ValueError(f"{app} tool installation failed")
        if not shutil.which(app):
            raise ValueError(
                f"{app} installed but unavailable on PATH; restart your terminal"
            )


def ensure_sentry(home, python):
    missing = 'No MCP server named "sentry".'
    existing = command(
        "claude",
        ["mcp", "get", "sentry"],
        home,
        parse_json=False,
        missing_message=missing,
    )
    if existing is not None:
        return
    spec = {"command": python, "args": [str(home / "sentry_mcp.py")]}
    command(
        "claude",
        ["mcp", "add-json", "--scope", "user", "sentry", json.dumps(spec)],
        home,
        parse_json=False,
    )
    command("claude", ["mcp", "get", "sentry"], home, parse_json=False)


def restore_preserving_flags(app, home, plugins):
    from .manage import parse
    from .config import render
    from .install import read, locked, recover, publish, fingerprint

    name = "settings.json" if app == "claude" else "config.toml"
    path = home / name
    before = parse(app, read(path))
    section = "enabledPlugins" if app == "claude" else "plugins"
    flags = before.get(section, {})
    effective = []
    for plugin in plugins:
        desired = dict(plugin)
        value = flags.get(plugin["id"])
        if app == "claude" and isinstance(value, bool):
            desired["enabled"] = value
        elif (
            app == "codex"
            and isinstance(value, dict)
            and isinstance(value.get("enabled"), bool)
        ):
            desired["enabled"] = value["enabled"]
        effective.append(desired)
    issues = restore(app, home, effective)
    with locked(home) as state:
        recover(home, state)
        current_bytes = read(path)
        current = parse(app, current_bytes)
        native_flags = current.setdefault(section, {})
        for plugin in plugins:
            identifier = plugin["id"]
            if identifier in flags:
                native_flags[identifier] = flags[identifier]
            else:
                native_flags.pop(identifier, None)
        output = (
            json.dumps(current, indent=2).encode() + b"\n"
            if app == "claude"
            else render(current)
        )
        if current != parse(app, current_bytes):
            baseline = json.loads((state / "baseline.json").read_text())
            publish(home, state, {name: (output, fingerprint(path))}, baseline)
    return issues

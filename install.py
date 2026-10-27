#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if sys.version_info < (3, 11):
    sys.exit("Python 3.11 or newer is required")
import tomllib

REPO = Path(__file__).resolve().parent
config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
orca_dir = os.environ.get("ORCA_CLAUDE_INJECTED_CONFIG_DIR")
# Orca points Claude at a profile directory built from ~/.claude, so ~/.claude is the one to install into.
ORCA_PROFILE = bool(config_dir and orca_dir) and Path(config_dir).resolve() == Path(orca_dir).resolve()
CLAUDE = Path.home() / ".claude" if ORCA_PROFILE or not config_dir else Path(config_dir)
CODEX = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
# `npx skills -g` ignores CLAUDE_CONFIG_DIR and always installs under the home directory.
SKILL_DIRS = {"claude-code": Path.home() / ".claude/skills", "codex": Path.home() / ".agents/skills"}
# The repo settings and Codex template as last installed, so a key or plugin removed from the repo
# can be removed from the live files.
INSTALLED_SETTINGS = CLAUDE / ".claude-config-settings.json"
INSTALLED_CONFIG = CODEX / ".claude-config-config.toml"
FAILED = []

FILES = {
    "claude/CLAUDE.md": [CLAUDE / "CLAUDE.md"],
    "claude/pstack-models.md": [CLAUDE / "pstack-models.md"],
    "claude/statusline.py": [CLAUDE / "statusline.py"],
    "claude/merge_guard.py": [CLAUDE / "merge_guard.py"],
    "claude/merge_cleanup.py": [CLAUDE / "merge_cleanup.py"],
    "claude/orca_cookie_guard.py": [CLAUDE / "orca_cookie_guard.py"],
    "codex/AGENTS.md": [CODEX / "AGENTS.md"],
    "codex/pstack-models.md": [CODEX / "pstack-models.md"],
    **{f"skills/{d.name}": [CLAUDE / "skills" / d.name, CODEX / "skills" / d.name]
       for d in (REPO / "skills").iterdir() if d.is_dir()},
    **{f"codex/skills/{d.name}": [CODEX / "skills" / d.name]
       for d in (REPO / "codex/skills").iterdir() if d.is_dir()},
}

MARKETPLACES = {
    "claude-community": "anthropics/claude-plugins-community",
    "claude-plugins-official": "anthropics/claude-plugins-official",
    "plannotator": "backnotprop/plannotator",
    "pstack-claude": "michael-denyer/pstack-claude",
    "visual-explainer-marketplace": "nicobailon/visual-explainer",
}

THIRD_PARTY_SKILLS = [
    ("vercel-labs/skills", ["find-skills"], ["codex"]),
    ("google/skills", ["finding-google-skills", "gcloud"], ["claude-code", "codex"]),
    ("cli/cli", ["gh"], ["claude-code", "codex"]),
    ("github/gh-stack", ["gh-stack"], ["claude-code", "codex"]),
    ("backnotprop/bro", ["status", "big-pics-little-words"], ["claude-code", "codex"]),
    ("nicobailon/visual-explainer", ["visual-explainer"], ["codex"]),
]


def replace_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and not path.is_symlink() and path.read_bytes() == data:
        return
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    print(f"wrote {path}")


def copy(source, dest):
    if source.is_dir():
        if dest.is_symlink() or getattr(os.path, "isjunction", lambda _: False)(dest):
            (os.rmdir if os.name == "nt" else os.unlink)(dest)
        for file in source.rglob("*"):
            if file.is_file():
                copy(file, dest / file.relative_to(source))
        for file in dest.rglob("*"):
            if file.is_file() and not (source / file.relative_to(dest)).is_file():
                file.unlink()
                print(f"removed {file}")
    else:
        replace_file(dest, source.read_bytes())


def overlay(live, repo):
    for key, value in repo.items():
        if isinstance(value, dict) and isinstance(live.get(key), dict):
            overlay(live[key], value)
        else:
            live[key] = value
    return live


def prune(live, before, after):
    for key, value in before.items():
        if isinstance(value, dict) and isinstance(live.get(key), dict):
            nested = after.get(key)
            prune(live[key], value, nested if isinstance(nested, dict) else {})
            if key not in after and not live[key]:
                del live[key]
        elif key not in after:
            live.pop(key, None)


def claude_settings():
    path = CLAUDE / "settings.json"
    live = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    source = (REPO / "claude/settings.json").read_bytes()
    repo = json.loads(source)
    before = json.loads(INSTALLED_SETTINGS.read_text(encoding="utf-8")) if INSTALLED_SETTINGS.exists() else {}
    prune(live, before, repo)
    settings = overlay(live, repo)
    settings["statusLine"] = {
        "type": "command",
        "command": f'"{sys.executable}" "{CLAUDE / "statusline.py"}"',
    }
    guard_args = [str(CLAUDE / "merge_guard.py")]
    guard = {
        "type": "command",
        "command": sys.executable,
        "args": guard_args,
        "timeout": 60,
        "onFailure": "block",
        "statusMessage": "Checking PR review threads",
    }
    cookie_guard = {
        "type": "command",
        "command": sys.executable,
        "args": [str(CLAUDE / "orca_cookie_guard.py")],
        "timeout": 10,
        "onFailure": "block",
        "statusMessage": "Checking for an Orca cookie wipe",
    }
    cleanup = {
        "type": "command",
        "command": sys.executable,
        "args": [str(CLAUDE / "merge_cleanup.py")],
        "timeout": 10,
    }
    ours = {"merge_guard.py", "orca_cookie_guard.py", "merge_cleanup.py"}
    installed = {
        "PreToolUse": [dict(guard, **{"if": "Bash(*gh*)"}), dict(guard, **{"if": "PowerShell(*gh*)"}),
                       dict(cookie_guard, **{"if": "Bash(*cookie*)"}),
                       dict(cookie_guard, **{"if": "PowerShell(*cookie*)"})],
        "PostToolUse": [dict(cleanup, **{"if": "Bash(*gh*)"}), dict(cleanup, **{"if": "PowerShell(*gh*)"})],
    }
    for event, ours_here in installed.items():
        hooks = settings.setdefault("hooks", {}).setdefault(event, [])
        for entry in hooks:
            entry["hooks"] = [h for h in entry["hooks"]
                              if not h.get("args") or Path(h["args"][-1]).name not in ours]
        hooks[:] = [entry for entry in hooks if entry["hooks"]]
        hooks.append({"matcher": "Bash|PowerShell", "hooks": ours_here})
    if path.is_symlink() or not path.exists() or settings != json.loads(path.read_text(encoding="utf-8")):
        replace_file(path, json.dumps(settings, indent=2).encode() + b"\n")
    # After a failed plugin step the snapshot keeps the old keys, so the next run still removes them.
    # The source is parsed again because `settings` holds `repo`'s objects and the hook code edits them.
    replace_file(INSTALLED_SETTINGS, json.dumps(overlay(before, json.loads(source)), indent=2).encode() + b"\n"
                 if FAILED else source)


def codex_config():
    path = CODEX / "config.toml"
    live = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    live.get("mcp_servers", {}).get("exa", {}).pop("bearer_token_env_var", None)
    source = (REPO / "codex/config.template.toml").read_bytes()
    repo = tomllib.loads(source.decode())
    before = tomllib.loads(INSTALLED_CONFIG.read_text(encoding="utf-8")) if INSTALLED_CONFIG.exists() else {}
    prune(live, before, repo)
    config = overlay(live, repo)
    # Codex rewrites this file in its own style, so only write when the values differ,
    # an older install left quoted keys that text-matching tools do not recognize, or
    # Codex wrote a ''' string ending in a quote (''''), which Bun's TOML parser rejects.
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if (path.is_symlink() or not path.exists() or config != tomllib.loads(text)
            or re.search(r'^\[*"[A-Za-z0-9_-]+"', text, re.M)
            or re.search(r"''''\s*$", text, re.M)):
        replace_file(path, toml(config))
    replace_file(INSTALLED_CONFIG, toml(overlay(before, repo)) if FAILED else source)


def toml(config):
    # Bare keys where TOML allows them: tools such as Plannotator's updater match `[features]` as text.
    def key(k):
        return k if k and all(c.isascii() and (c.isalnum() or c in "_-") for c in k) else json.dumps(k)

    def scalar(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, list):
            return "[" + ", ".join(scalar(v) for v in value) + "]"
        if isinstance(value, dict):
            return "{" + ", ".join(f"{key(k)} = {scalar(v)}" for k, v in value.items()) + "}"
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        return value.isoformat()

    lines = []

    def table(value, path):
        if path:
            lines.extend(["", "[" + ".".join(key(k) for k in path) + "]"])
        lines.extend(f"{key(k)} = {scalar(v)}" for k, v in value.items() if not isinstance(v, dict))
        for k, item in value.items():
            if isinstance(item, dict):
                table(item, path + (k,))

    table(config, ())
    data = "\n".join(lines).lstrip("\n") + "\n"
    if tomllib.loads(data) != config:
        raise ValueError("TOML serialization changed the Codex config")
    return data.encode()


def run(*argv):
    executable = shutil.which(argv[0])
    if not executable:
        print(f"skipped `{' '.join(argv)}`: {argv[0]} not on PATH")
        return None
    env = dict(os.environ)
    if ORCA_PROFILE:
        env.pop("CLAUDE_CONFIG_DIR")
    if os.name == "nt":
        n = int(env.get("GIT_CONFIG_COUNT") or 0)
        env.update({"GIT_CONFIG_COUNT": str(n + 1), f"GIT_CONFIG_KEY_{n}": "core.longpaths",
                    f"GIT_CONFIG_VALUE_{n}": "true"})
    result = subprocess.run([executable, *argv[1:]], env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=600)
    remote_list_failed = (argv[:3] == ("codex", "plugin", "list")
                          and "Warning: failed to list remote marketplace plugins:" in result.stderr)
    if result.returncode or remote_list_failed:
        print(f"failed `{' '.join(argv)}`: {result.stderr.strip()}", file=sys.stderr)
        FAILED.append(argv)
        return None
    return result.stdout


def enabled_plugins(app, path):
    if not path.exists():
        return {}
    if app == "claude":
        return json.loads(path.read_text(encoding="utf-8")).get("enabledPlugins", {})
    plugins = tomllib.loads(path.read_text(encoding="utf-8")).get("plugins", {})
    # Codex treats a plugin table without `enabled` as enabled.
    return {name: value.get("enabled", True) for name, value in plugins.items()}


def install_plugins(app, enabled):
    scope = ["--scope", "user"] if app == "claude" else []
    before = enabled_plugins(app, INSTALLED_SETTINGS if app == "claude" else INSTALLED_CONFIG)
    installed = run(app, "plugin", "list", "--json")
    if installed is None:
        return
    listing = json.loads(installed)
    if app == "codex":
        installed = {row["pluginId"] for row in listing["installed"]}
    else:
        installed = {row["id"] for row in listing}
    marketplaces = run(app, "plugin", "marketplace", "list", "--json")
    if marketplaces is None:
        return
    rows = json.loads(marketplaces)
    if app == "codex":
        rows = rows["marketplaces"]
    known = {row["name"] for row in rows}
    dropped = {plugin for plugin, on in before.items() if on and plugin not in enabled}
    for plugin in dropped & installed:
        run(app, "plugin", "uninstall" if app == "claude" else "remove", plugin, *scope)
    # Keep a marketplace that the repo or a plugin installed outside the repo still uses.
    in_use = {plugin.split("@")[1] for plugin in (installed - dropped) | enabled.keys()} | MARKETPLACES.keys()
    for marketplace in {plugin.split("@")[1] for plugin in dropped} - in_use:
        if marketplace in known:
            run(app, "plugin", "marketplace", "remove", marketplace)
    for plugin, on in enabled.items():
        marketplace = plugin.split("@")[1]
        if not on or plugin in installed or marketplace not in MARKETPLACES:
            continue
        if marketplace not in known:
            # Claude rejects a source that differs from its extraKnownMarketplaces entry.
            source = MARKETPLACES[marketplace]
            run(app, "plugin", "marketplace", "add",
                source if app == "claude" else f"https://github.com/{source}.git", *scope)
            known.add(marketplace)
        run(app, "plugin", "install" if app == "claude" else "add", plugin, *scope)


def install_third_party_skills():
    for source, skills, agents in THIRD_PARTY_SKILLS:
        if all((SKILL_DIRS[a] / s / "SKILL.md").is_file() for a in agents for s in skills):
            continue
        run("npx", "--yes", "skills", "add", source, "--skill", *skills, "-g", "-a", *agents, "--copy", "-y")


if __name__ == "__main__":
    if ORCA_PROFILE:
        print(f"ignored the CLAUDE_CONFIG_DIR Orca set; installing into {CLAUDE}")
    for source, destinations in FILES.items():
        for dest in destinations:
            copy(REPO / source, dest)
    # The plugin CLIs rewrite settings as they install, so the repo's config is written after them.
    install_plugins("claude", enabled_plugins("claude", REPO / "claude/settings.json"))
    install_plugins("codex", enabled_plugins("codex", REPO / "codex/config.template.toml"))
    claude_settings()
    codex_config()
    install_third_party_skills()
    sys.exit(1 if FAILED else 0)

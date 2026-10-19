#!/usr/bin/env python3
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if sys.version_info < (3, 11):
    sys.exit("Python 3.11 or newer is required")
import tomllib

REPO = Path(__file__).resolve().parent
CLAUDE = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
CODEX = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
SKILL_DIRS = {"claude-code": CLAUDE / "skills", "codex": Path.home() / ".agents/skills"}

FILES = {
    "CLAUDE.md": [CLAUDE / "CLAUDE.md"],
    "pstack-models.md": [CLAUDE / "pstack-models.md"],
    "statusline.py": [CLAUDE / "statusline.py"],
    "merge_guard.py": [CLAUDE / "merge_guard.py"],
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
    "pstack-claude": "michael-denyer/pstack-claude",
    "visual-explainer-marketplace": "nicobailon/visual-explainer",
    "worktrunk": "max-sixty/worktrunk",
}

THIRD_PARTY_SKILLS = [
    ("vercel-labs/skills", ["find-skills"], ["codex"]),
    ("google/skills", ["finding-google-skills", "gcloud"], ["claude-code", "codex"]),
    ("cli/cli", ["gh"], ["claude-code", "codex"]),
    ("github/gh-stack", ["gh-stack"], ["claude-code", "codex"]),
    ("backnotprop/bro", ["status"], ["claude-code", "codex"]),
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
        for file in source.rglob("*"):
            if file.is_file():
                copy(file, dest / file.relative_to(source))
    else:
        replace_file(dest, source.read_bytes())


def overlay(live, repo):
    for key, value in repo.items():
        if isinstance(value, dict) and isinstance(live.get(key), dict):
            overlay(live[key], value)
        else:
            live[key] = value
    return live


def claude_settings():
    path = CLAUDE / "settings.json"
    live = json.loads(path.read_text()) if path.exists() else {}
    settings = overlay(live, json.loads((REPO / "settings.json").read_text()))
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
    hooks = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    for entry in hooks:
        entry["hooks"] = [h for h in entry.get("hooks", [])
                          if not str((h.get("args") or [""])[-1]).endswith("merge_guard.py")]
    hooks[:] = [entry for entry in hooks if entry["hooks"]]
    hooks.append({
        "matcher": "Bash|PowerShell",
        "hooks": [dict(guard, **{"if": "Bash(*gh*)"}), dict(guard, **{"if": "PowerShell(*gh*)"})],
    })
    if path.is_symlink() or not path.exists() or settings != json.loads(path.read_text()):
        replace_file(path, json.dumps(settings, indent=2).encode() + b"\n")
    return settings["enabledPlugins"]


def codex_config():
    path = CODEX / "config.toml"
    live = tomllib.loads(path.read_text()) if path.exists() else {}
    config = overlay(live, tomllib.loads((REPO / "codex/config.template.toml").read_text()))
    # Codex rewrites this file in its own style, so only write when the values differ.
    if path.is_symlink() or not path.exists() or config != tomllib.loads(path.read_text()):
        replace_file(path, toml(config))
    return {name: value["enabled"] for name, value in config.get("plugins", {}).items()}


def toml(config):
    def scalar(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, list):
            return "[" + ", ".join(scalar(v) for v in value) + "]"
        if isinstance(value, dict):
            return "{" + ", ".join(f"{json.dumps(k)} = {scalar(v)}" for k, v in value.items()) + "}"
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        return value.isoformat()

    lines = []

    def table(value, path):
        if path:
            lines.extend(["", "[" + ".".join(json.dumps(k) for k in path) + "]"])
        lines.extend(f"{json.dumps(k)} = {scalar(v)}" for k, v in value.items() if not isinstance(v, dict))
        for key, item in value.items():
            if isinstance(item, dict):
                table(item, path + (key,))

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
    if os.name == "nt":
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.longpaths", GIT_CONFIG_VALUE_0="true")
    result = subprocess.run([executable, *argv[1:]], env=env, capture_output=True, text=True, timeout=600)
    if result.returncode:
        print(f"failed `{' '.join(argv)}`: {result.stderr.strip()}", file=sys.stderr)
        return None
    return result.stdout


def names(listing, key):
    rows = json.loads(listing or "[]")
    rows = rows.get(key, []) if isinstance(rows, dict) else rows
    return {row.get("id") or row.get("pluginId") or row.get("name") for row in rows}


def install_plugins(app, enabled):
    scope = ["--scope", "user"] if app == "claude" else []
    installed = run(app, "plugin", "list", "--json")
    if installed is None:
        return
    installed = names(installed, "installed")
    known = names(run(app, "plugin", "marketplace", "list", "--json"), "marketplaces")
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
    for source, destinations in FILES.items():
        for dest in destinations:
            copy(REPO / source, dest)
    install_plugins("claude", claude_settings())
    install_plugins("codex", codex_config())
    install_third_party_skills()

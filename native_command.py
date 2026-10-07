import os
from pathlib import Path
import shutil


NPM_ENTRY_POINTS = {
    "claude": "node_modules/@anthropic-ai/claude-code/bin/claude.exe",
    "codex": "node_modules/@openai/codex/bin/codex.js",
    "npm": "node_modules/npm/bin/npm-cli.js",
    "npx": "node_modules/npm/bin/npx-cli.js",
}


def argv_for(name, arguments):
    executable = shutil.which(name)
    if not executable:
        raise ValueError(f"{name} executable missing; install it and add it to PATH")
    if os.name != "nt" or Path(executable).suffix.lower() not in (".cmd", ".bat"):
        return [executable, *arguments]
    entry = NPM_ENTRY_POINTS.get(name)
    script = Path(executable).parent / entry if entry else None
    if script is not None and script.is_file() and script.suffix.lower() == ".exe":
        return [str(script), *arguments]
    node = shutil.which("node")
    if not node and (Path(executable).parent / "node.exe").is_file():
        node = str(Path(executable).parent / "node.exe")
    if script is None or not script.is_file() or not node:
        raise ValueError(
            f"{name} requires a native executable or a standard Node/npm installation"
        )
    if Path(node).suffix.lower() in (".cmd", ".bat"):
        raise ValueError("Node must be a native executable")
    return [node, str(script), *arguments]

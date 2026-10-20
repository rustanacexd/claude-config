#!/usr/bin/env python3
"""Update every installed Claude Code and Codex plugin. install.py schedules this on macOS."""
from datetime import datetime
import json
import shutil
import subprocess
import sys

FAILED = []


def run(*argv):
    command = " ".join(argv)
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        print(f"failed `{command}`: timed out after 600s")
        FAILED.append(argv)
        return None
    if result.returncode:
        print(f"failed `{command}`: {result.stderr.strip() or result.stdout.strip()}")
        FAILED.append(argv)
        return None
    return result.stdout


def update(name, *argv):
    if run(*argv) is not None:
        print(f"updated {name}")


if __name__ == "__main__":
    # launchd sends stdout to a file, so flush each line in case the run is killed.
    sys.stdout.reconfigure(line_buffering=True)
    print(datetime.now().astimezone().isoformat(timespec="seconds"))
    if shutil.which("claude"):
        update("claude marketplaces", "claude", "plugin", "marketplace", "update")
        for plugin in json.loads(run("claude", "plugin", "list", "--json") or "[]"):
            # No -y: without a TTY the CLI refuses a changed marketplace-declared command,
            # and that refusal should be reported, not accepted unattended.
            update(plugin["id"], "claude", "plugin", "update", plugin["id"], "--scope", plugin["scope"])
    else:
        print("skipped claude: not on PATH")
    if shutil.which("codex"):
        # Keep going after a failed upgrade, because one slow clone should not hold back the other plugins.
        update("codex marketplaces", "codex", "plugin", "marketplace", "upgrade")
        for plugin in json.loads(run("codex", "plugin", "list", "--json") or "{}").get("installed", []):
            # The Codex app manages local, bundled, and remote marketplaces itself.
            if (plugin.get("marketplaceSource") or {}).get("sourceType") == "git":
                update(plugin["pluginId"], "codex", "plugin", "add", plugin["pluginId"])
    else:
        print("skipped codex: not on PATH")
    sys.exit(1 if FAILED else 0)

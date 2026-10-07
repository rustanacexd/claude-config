#!/usr/bin/env python3

import json
import os
from pathlib import Path
import subprocess
import sys


def humanize(number):
    for limit, suffix in ((1000000, "M"), (1000, "k")):
        if number >= limit:
            return f"{number / limit:.1f}".rstrip("0").rstrip(".") + suffix
    return str(int(number))


def format_status(data):
    cwd = data.get("workspace", {}).get("current_dir", data.get("cwd", "."))
    path = str(cwd).replace(str(Path.home()), "~", 1)
    parts = path.replace("\\", "/").split("/")
    if len(parts) > 3:
        path = ".../" + "/".join(parts[-3:])
    result = [f"\033[34m{path}\033[0m"]
    try:
        for args in (
            ["symbolic-ref", "--short", "HEAD"],
            ["rev-parse", "--short", "HEAD"],
        ):
            git = subprocess.run(
                ["git", "--no-optional-locks", "-C", cwd, *args],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if git.returncode == 0:
                result.append(f"\033[33m{git.stdout.strip()}\033[0m")
                break
    except (OSError, subprocess.TimeoutExpired):
        pass
    model = data.get("model", {}).get("display_name", "Claude").split(" (")[0]
    result.append(f"\033[35m{model}\033[0m")
    effort = data.get("effort", {}).get("level")
    if effort:
        result.append(f"\033[36m{effort}\033[0m")
    context = data.get("context_window", {})
    used = context.get("total_input_tokens")
    size = context.get("context_window_size")
    if used is not None:
        ceiling = os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
        pct = context.get("used_percentage", 0)
        if ceiling and size and int(ceiling) < size:
            size = int(ceiling)
            pct = used * 100 / size
        color = 31 if pct >= 80 else 33 if pct >= 50 else 32
        tokens = humanize(used) + (("/" + humanize(size)) if size else "")
        result.append(f"\033[{color}m{tokens}\033[0m")
    pr = data.get("pr", {})
    if pr.get("number") and pr.get("url"):
        result.append(
            f"\033[96m\033]8;;{pr['url']}\033\\PR #{pr['number']}\033]8;;\033\\\033[0m"
        )
    mode = data.get("vim", {}).get("mode")
    if mode:
        result.append(f"\033[38;5;208m[{mode.lower()}]\033[0m")
    return " ".join(result)


if __name__ == "__main__":
    try:
        print(format_status(json.load(sys.stdin)), end="")
    except (ValueError, TypeError):
        pass

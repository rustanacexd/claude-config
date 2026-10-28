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
    cwd = data["workspace"]["current_dir"]
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
    model = data["model"]["display_name"].split(" (")[0]
    result.append(f"\033[35m{model}\033[0m")
    effort = data.get("effort")
    if effort is not None:
        result.append(f"\033[36m{effort['level']}\033[0m")
    context = data["context_window"]
    used = context["total_input_tokens"]
    size = context["context_window_size"]
    ceiling = os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
    if not ceiling:
        try:
            settings = json.loads((Path.home() / ".claude" / "settings.json").read_text())
            ceiling = settings.get("autoCompactWindow")
        except (OSError, ValueError):
            pass
    pct = context["used_percentage"] or 0
    if ceiling and int(ceiling) < size:
        size = int(ceiling)
        pct = used * 100 / size
    color = 31 if pct >= 80 else 33 if pct >= 50 else 32
    tokens = humanize(used) + "/" + humanize(size)
    result.append(f"\033[{color}m{tokens}\033[0m")
    pr = data.get("pr")
    if pr is not None:
        result.append(
            f"\033[96m\033]8;;{pr['url']}\033\\PR #{pr['number']}\033]8;;\033\\\033[0m"
        )
    vim = data.get("vim")
    if vim is not None:
        result.append(f"\033[38;5;208m[{vim['mode'].lower()}]\033[0m")
    return " ".join(result)


if __name__ == "__main__":
    try:
        print(format_status(json.load(sys.stdin)), end="")
    except (ValueError, TypeError):
        pass

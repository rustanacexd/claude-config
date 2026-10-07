#!/usr/bin/env python3

import os
from pathlib import Path
import sys

if sys.version_info < (3, 11):
    sys.exit("Python 3.11 or newer is required")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portable.manage import refresh as reconcile


def refresh(repo, home):
    return reconcile(Path(repo).resolve().parent, {"codex": Path(home)}, ["codex"])


if __name__ == "__main__":
    try:
        refresh(
            Path(__file__).resolve().parent,
            Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))),
        )
    except (ValueError, OSError) as error:
        print(f"Codex refresh failed: {error}", file=sys.stderr)
        sys.exit(1)

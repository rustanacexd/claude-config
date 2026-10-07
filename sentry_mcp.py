#!/usr/bin/env python3
"""Run Go2 Sentry MCP with per-machine environment authentication."""

import os
import shutil
import subprocess
import sys

if __name__ == "__main__":
    if not os.environ.get("SENTRY_ACCESS_TOKEN"):
        sys.exit("SENTRY_ACCESS_TOKEN is missing")
    executable = shutil.which("npx")
    if not executable:
        sys.exit("Install Node/npm to run Sentry MCP")
    argv = [
        executable,
        "--yes",
        "@sentry/mcp-server@0.42.0",
        "--host=sentry-hosted.go2.io",
        "--organization-slug=go2",
    ]
    if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
        argv = [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/s",
            "/c",
            subprocess.list2cmdline(argv),
        ]
    sys.exit(subprocess.call(argv))

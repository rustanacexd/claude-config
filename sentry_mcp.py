#!/usr/bin/env python3

import os
import subprocess
import sys
from native_command import argv_for

if __name__ == "__main__":
    if not os.environ.get("SENTRY_ACCESS_TOKEN"):
        sys.exit("SENTRY_ACCESS_TOKEN is missing")
    arguments = [
        "--yes",
        "@sentry/mcp-server@0.42.0",
        "--host=sentry-hosted.go2.io",
        "--organization-slug=go2",
    ]
    try:
        argv = argv_for("npx", arguments)
    except ValueError as error:
        sys.exit(str(error))
    sys.exit(subprocess.call(argv))

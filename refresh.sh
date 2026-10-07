#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "${1:-}" = "--codex-only" ]; then
  shift
  exec python3 "$ROOT/manage.py" refresh --app codex "$@"
fi
exec python3 "$ROOT/manage.py" refresh "$@"

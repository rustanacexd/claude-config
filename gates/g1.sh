#!/bin/sh
# Any non-zero exit from Python, 127 included, becomes 2: Claude Code runs the command on any other code.
HOOK="$(dirname "$0")/hook.py"
in=$(cat)
case "$in" in
  *"gh pr merge"*) printf %s "$in" | python3 -S -E "$HOOK"; rc=$?; [ $rc -eq 0 ] && exit 0; exit 2 ;;
  *) exit 0 ;;
esac

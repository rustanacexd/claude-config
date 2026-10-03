#!/bin/sh
# Exit 2 from Python is a block. Any other non-zero exit, 127 included, also blocks, because Claude Code runs the
# call on any code but 2. On Stop and SessionStart it allows instead, because a crashing Stop gate would keep every
# session from ending.
[ -e "$HOME/.claude/gates.off" ] && exit 0
HOOK="$(dirname "$0")/hook.py"
in=$(cat)
if [ "$1" = PreToolUse ] && [ "$2" = Bash ]; then
  case "$in" in
    *"gh pr merge"* | *"gh stack merge"* | *"gh pr create"* | *"gh stack submit"* | *"git commit"* | *"git push"* | *"--no-verify"*) ;;
    *"git -"*" commit"* | *"git -"*" push"*) ;;
    *) exit 0 ;;
  esac
fi
if [ -r "$HOOK" ]; then
  printf %s "$in" | python3 -S -E "$HOOK" "$1"
  rc=$?
else
  rc=127
fi
case "$rc:$1" in
  0:* | 2:*) exit $rc ;;
  *:Stop | *:SessionStart) printf '{"systemMessage": "The workflow gate crashed (exit %s), so it did not check this %s. The bug is in ~/.claude/gates."}\n' "$rc" "$1"; exit 0 ;;
  *) exit 2 ;;
esac

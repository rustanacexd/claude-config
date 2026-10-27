#!/usr/bin/env python3
"""Claude Code PostToolUse hook: after a PR merge, tell the agent to clean up branches.

Agents kept merging PRs and leaving the topic branches behind, although AGENTS.md asks
for cleanup. This hook puts that rule in front of the agent right after `gh pr merge`
or `gh stack merge` succeeds.
"""

import json
import sys

from merge_guard import ASSIGNMENT, is_gh, merges, segments

CLEANUP = """A PR was just merged. Clean up branches before you report back:
- Fetch and prune every remote.
- Delete the local and remote topic branches whose tips are confirmed merged into the
  remote's default branch. For a squash or rebase merge, confirm the merged PR's exact head
  commit equals the branch tip; keep a branch that has newer, unmerged commits.
- Keep default and protected branches, and branches checked out in any worktree.
- Report each branch you skipped and why."""


def stack_merge(words):
    words = [word for word in words if not ASSIGNMENT.match(word)]
    return is_gh(words) and words[1:3] == ["stack", "merge"]


def merged(command):
    try:
        if any(True for _ in merges(command)):
            return True
        return any(stack_merge(part) for part in segments(command) if part)
    except ValueError:
        return False


def main():
    event = json.load(sys.stdin)
    if merged(event.get("tool_input", {}).get("command", "")):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                 "additionalContext": CLEANUP}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

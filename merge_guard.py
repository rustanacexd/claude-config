#!/usr/bin/env python3
"""Claude Code PreToolUse hook: refuse `gh pr merge` while review threads are open.

GitHub reports a PR as CLEAN when branch protection does not require resolved
conversations, so mergeability alone lets open findings land. When the threads
cannot be read, the merge is refused too.
"""

import json
import os
import re
import shlex
import subprocess
import sys

QUERY = """
query($owner:String!,$name:String!,$number:Int!){
  repository(owner:$owner,name:$name){pullRequest(number:$number){
    reviewThreads(first:100){nodes{isResolved isOutdated path line
      comments(first:1){nodes{author{login} body}}}}}}}
"""


def merges(command):
    for segment in re.findall(r"gh pr merge[^;&|\n]*", command):
        try:
            words = shlex.split(segment)[3:]
        except ValueError:
            words = segment.split()[3:]
        target, repo, i = None, [], 0
        while i < len(words):
            word = words[i]
            if word in ("-R", "--repo"):
                repo = ["--repo", words[i + 1] if i + 1 < len(words) else ""]
                i += 1
            elif word.startswith("--repo="):
                repo = ["--repo", word.split("=", 1)[1]]
            elif not word.startswith("-") and target is None:
                target = word
            i += 1
        yield ([target] if target else []) + repo


def gh(args, cwd):
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, cwd=cwd, timeout=20
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def summary(thread):
    comment = (thread["comments"]["nodes"] or [{}])[0]
    body = re.sub(r"<[^>]*>|!\[[^\]]*\]\([^)]*\)|\*\*", "", comment.get("body", ""))
    first = next((s.strip() for s in body.splitlines() if re.search("[A-Za-z]", s)), "")
    author = (comment.get("author") or {}).get("login", "?")
    outdated = " (outdated)" if thread["isOutdated"] else ""
    return f"- {thread['path']}:{thread['line'] or '?'} [{author}]{outdated} {first[:120]}"


def check(args, cwd):
    url = gh(["pr", "view", *args, "--json", "url", "-q", ".url"], cwd).strip()
    match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", url)
    if not match:
        raise RuntimeError(f"unexpected PR URL {url!r}")
    owner, name, number = match.groups()
    data = json.loads(
        gh(["api", "graphql", "-F", f"owner={owner}", "-F", f"name={name}",
            "-F", f"number={number}", "-f", f"query={QUERY}"], cwd)
    )
    threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    open_threads = [summary(t) for t in threads if not t["isResolved"]]
    if open_threads:
        return [f"Merge blocked: {url} has {len(open_threads)} unresolved review thread(s):",
                *open_threads,
                "Triage each one: fix it or reply with why not, then resolve the thread. "
                "Rerun the merge only when none are open."]
    return []


def main():
    event = json.load(sys.stdin)
    command = event.get("tool_input", {}).get("command", "")
    if "gh pr merge" not in command:
        return 0
    cwd = event.get("cwd")
    cwd = cwd if cwd and os.path.isdir(cwd) else None
    for args in merges(command):
        try:
            problems = check(args, cwd)
        except (RuntimeError, OSError, subprocess.TimeoutExpired, KeyError, TypeError, ValueError) as error:
            problems = ["Merge blocked: could not read the PR's review threads.", str(error)]
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

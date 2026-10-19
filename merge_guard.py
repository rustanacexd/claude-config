#!/usr/bin/env python3
"""Claude Code PreToolUse hook: refuse `gh pr merge` while review threads are open.

GitHub reports a PR as CLEAN when branch protection does not require resolved
conversations, so mergeability alone lets open findings land. When the threads
cannot be read, the merge is refused too. `--auto` is refused because the PR
lands later, after this check can no longer see new threads.
"""

import json
import os
import re
import shlex
import subprocess
import sys

QUERY = """
query($owner:String!,$name:String!,$number:Int!,$after:String){
  repository(owner:$owner,name:$name){pullRequest(number:$number){
    reviewThreads(first:100,after:$after){pageInfo{hasNextPage endCursor}
      nodes{isResolved isOutdated path line
        comments(first:1){nodes{author{login} body}}}}}}}
"""

SEPARATORS = set(";&|()\n")
VALUE_FLAGS = {"-R", "--repo", "-b", "--body", "-F", "--body-file", "-t", "--subject",
               "-A", "--author-email", "--match-head-commit"}


def segments(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    segment = []
    for token in lexer:
        if set(token) <= SEPARATORS:
            yield segment
            segment = []
        else:
            segment.append(token)
    yield segment


def merge_args(words):
    """Return the `gh pr merge` arguments in one simple command, or None."""
    names = [re.sub(r"\.exe$", "", os.path.basename(w.lstrip("`$")), flags=re.I) for w in words]
    if "gh" not in names:
        return None
    words = words[names.index("gh") + 1:]
    repo, i = [], 0
    while i < len(words) and words[i].startswith("-"):
        if words[i] in ("-R", "--repo"):
            repo = ["--repo", words[i + 1] if i + 1 < len(words) else ""]
            i += 1
        elif words[i].startswith("--repo="):
            repo = ["--repo", words[i].split("=", 1)[1]]
        i += 1
    if words[i:i + 2] != ["pr", "merge"]:
        return None
    return repo, words[i + 2:]


def merges(command):
    """Yield (gh pr view args, auto) per merge, or None to skip a disable-auto call."""
    for words in segments(command):
        found = merge_args(words)
        if found is None:
            continue
        repo, words = found
        target, auto, disable, i = None, False, False, 0
        while i < len(words):
            word = words[i]
            if word in VALUE_FLAGS:
                if word in ("-R", "--repo") and i + 1 < len(words):
                    repo = ["--repo", words[i + 1]]
                i += 1
            elif word.startswith("--repo="):
                repo = ["--repo", word.split("=", 1)[1]]
            elif word == "--auto":
                auto = True
            elif word == "--disable-auto":
                disable = True
            elif not word.startswith("-") and target is None:
                target = word
            i += 1
        if not disable:
            yield ([target] if target else []) + repo, auto


def gh(args, cwd):
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, cwd=cwd, timeout=15
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


def threads(url, cwd):
    match = re.search(r"https?://([^/]+)/([^/]+)/([^/]+)/pull/(\d+)", url)
    if not match:
        raise RuntimeError(f"unexpected PR URL {url!r}")
    host, owner, name, number = match.groups()
    after = []
    while True:
        data = json.loads(gh(["api", "graphql", "--hostname", host, "-F", f"owner={owner}",
                              "-F", f"name={name}", "-F", f"number={number}", *after,
                              "-f", f"query={QUERY}"], cwd))
        page = data["data"]["repository"]["pullRequest"]["reviewThreads"]
        yield from page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return
        after = ["-f", f"after={page['pageInfo']['endCursor']}"]


def check(args, auto, cwd):
    url = gh(["pr", "view", *args, "--json", "url", "-q", ".url"], cwd).strip()
    if auto:
        return [f"Merge blocked: {url} with --auto lands after this check runs, so a thread "
                "opened before checks finish would land unseen.",
                "Wait for the required checks, resolve every thread, then merge without --auto."]
    open_threads = [summary(t) for t in threads(url, cwd) if not t["isResolved"]]
    if open_threads:
        return [f"Merge blocked: {url} has {len(open_threads)} unresolved review thread(s):",
                *open_threads,
                "Triage each one: fix it or reply with why not, then resolve the thread. "
                "Rerun the merge only when none are open."]
    return []


def main():
    event = json.load(sys.stdin)
    command = event.get("tool_input", {}).get("command", "")
    if not re.search(r"\bgh\b", command) or not re.search(r"\bmerge\b", command):
        return 0
    cwd = event.get("cwd")
    cwd = cwd if cwd and os.path.isdir(cwd) else None
    try:
        found = list(merges(command))
    except ValueError as error:
        print(f"Merge blocked: could not parse the command ({error}).", file=sys.stderr)
        return 2
    for args, auto in found:
        try:
            problems = check(args, auto, cwd)
        except (RuntimeError, OSError, subprocess.TimeoutExpired, KeyError, TypeError, ValueError) as error:
            problems = ["Merge blocked: could not read the PR's review threads.", str(error)]
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Claude Code PreToolUse hook: refuse `gh pr merge` while review threads are open.

GitHub reports a PR as CLEAN when branch protection does not require resolved
conversations, so mergeability alone lets open findings land. When the threads
cannot be read, the merge is refused too. `--auto` and merge queues are refused
because the PR lands later, after this check can no longer see new threads.
"""

import json
import os
import re
import shlex
import subprocess
import sys

QUERY = """
query($owner:String!,$name:String!,$number:Int!,$after:String){
  repository(owner:$owner,name:$name){pullRequest(number:$number){isMergeQueueEnabled
    reviewThreads(first:100,after:$after){pageInfo{hasNextPage endCursor}
      nodes{isResolved isOutdated path line
        comments(first:1){nodes{author{login} body}}}}}}}
"""

SEPARATORS = set(";&|()<>\n")
VALUE_FLAGS = {"-R", "--repo", "-b", "--body", "-F", "--body-file", "-t", "--subject",
               "-A", "--author-email", "--match-head-commit"}
MERGE_TEXT = re.compile(r"\bgh(\.exe)?\b[^;&|\n]*\bpr\b[^;&|\n]*\bmerge\b", re.I)
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
ALONE = "run `gh pr merge <number> --repo OWNER/REPO` on its own"


def repo_flag(words, i):
    """Return (repo args, words consumed) when words[i] selects a repository."""
    word = words[i]
    if word in ("-R", "--repo"):
        return ["--repo", words[i + 1] if i + 1 < len(words) else ""], 2
    if word.startswith("--repo="):
        return ["--repo", word.split("=", 1)[1]], 1
    if word.startswith("-R") and len(word) > 2:
        return ["--repo", word[2:].removeprefix("=")], 1
    return None, 0


def boolean(word, name):
    """Return the value of --name or --name=value, or None when word is another flag."""
    if word == name:
        return True
    if word.startswith(name + "="):
        return word.split("=", 1)[1].lower() not in ("false", "0")
    return None


def expands(command):
    """Whether the shell would expand $ or a backtick anywhere in command."""
    quote, escaped = None, False
    for char in command:
        if escaped:
            escaped = False
        elif quote == "'":
            quote = None if char == "'" else quote
        elif char == "\\":
            escaped = True
        elif char in "$`":
            return True
        elif char == '"':
            quote = None if quote == '"' else '"'
        elif char == "'" and quote is None:
            quote = "'"
    return False


def segments(command):
    # Newline separates commands outside quotes, so it is punctuation here.
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
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


def is_gh(words):
    words = list(words)
    while words and ASSIGNMENT.match(words[0]):
        words.pop(0)
    # Suffix match: POSIX shlex drops the backslashes of a Windows path.
    return bool(words) and re.search(r"gh(\.exe)?$", words[0], re.I) is not None


def parse(words):
    """Return (gh pr view args, env, flags) when words run `gh pr merge`, else None."""
    if not is_gh(words):
        return None
    words, env = list(words), {}
    while ASSIGNMENT.match(words[0]):
        name, value = words.pop(0).split("=", 1)
        env[name] = value
    words = words[1:]
    repo = ["--repo", env["GH_REPO"]] if "GH_REPO" in env else []
    i = 0
    for command_name in ("pr", "merge"):
        # gh and gh pr both take -R/--repo before their subcommand.
        while i < len(words) and words[i].startswith("-"):
            found, used = repo_flag(words, i)
            repo = found or repo
            i += used or 1
        if i < len(words) and ("$" in words[i] or "`" in words[i]):
            raise ValueError(f"a gh subcommand comes from shell expansion; {ALONE}")
        if words[i:i + 1] != [command_name]:
            return None
        i += 1
    words = words[i:]
    target, flags, i = None, {"auto": False, "disable": False, "admin": False, "help": False}, 0
    while i < len(words):
        word = words[i]
        if word == "--":
            target = target or (words[i + 1] if i + 1 < len(words) else None)
            break
        found, used = repo_flag(words, i)
        if found:
            repo = found
            i += used
            continue
        if word in ("-h", "--help"):
            flags["help"] = True
        for key, flag in (("auto", "--auto"), ("disable", "--disable-auto"), ("admin", "--admin")):
            value = boolean(word, flag)
            if value is not None:
                flags[key] = value
                break
        else:
            if word in VALUE_FLAGS:
                i += 1
            elif not word.startswith("-") and target is None:
                target = word
        i += 1
    return ([target] if target else []) + repo, env, flags


def wraps_merge(words):
    """Whether words, not themselves a gh command, may run `pr merge`."""
    if any(MERGE_TEXT.search(word) for word in words):
        return True
    return "pr" in words and "merge" in words[words.index("pr"):]


def merges(command):
    """Yield (gh pr view args, env, flags) for the merge in command.

    Only a lone, literal `gh pr merge` is read. Any other command that runs or
    mentions one raises ValueError, since shell composition can change what it
    merges.
    """
    # Bash joins backslash-newline and PowerShell joins backtick-newline.
    command = re.sub(r"[\\`]\r?\n", "", command)
    try:
        parts = [part for part in segments(command) if part]
    except ValueError:
        if re.search("merge", re.sub(r"[\"'\\`]", "", command), re.I):
            raise
        return
    found = [merge for merge in map(parse, parts) if merge is not None]
    if not found:
        # A gh command parse() read is not a merge; anything else may wrap one.
        if any(wraps_merge(part) for part in parts if not is_gh(part)):
            raise ValueError(f"`gh pr merge` appears in a form the guard cannot read; {ALONE}")
        return
    if len(parts) > 1:
        raise ValueError(f"the merge is combined with other shell syntax; {ALONE}")
    if expands(command):
        raise ValueError(f"the merge uses shell expansion; {ALONE}")
    args, env, flags = found[0]
    if not flags["disable"] and not flags["help"]:
        yield args, env, flags


def gh(args, cwd, env):
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, cwd=cwd, timeout=15,
        env=dict(os.environ, **env),
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def summary(thread):
    comments = thread["comments"]["nodes"]
    comment = comments[0] if comments else None
    body = re.sub(r"<[^>]*>|!\[[^\]]*\]\([^)]*\)|\*\*", "", comment["body"] if comment is not None else "")
    first = next((s.strip() for s in body.splitlines() if re.search("[A-Za-z]", s)), "")
    author = comment["author"] if comment is not None else None
    author = author["login"] if author is not None else "?"
    outdated = " (outdated)" if thread["isOutdated"] else ""
    return f"- {thread['path']}:{thread['line'] or '?'} [{author}]{outdated} {first[:120]}"


class Deferred(Exception):
    pass


def threads(url, cwd, env, queue_defers):
    match = re.search(r"https?://([^/]+)/([^/]+)/([^/]+)/pull/(\d+)", url)
    if not match:
        raise RuntimeError(f"unexpected PR URL {url!r}")
    host, owner, name, number = match.groups()
    after, first = [], True
    while True:
        data = json.loads(gh(["api", "graphql", "--hostname", host, "-F", f"owner={owner}",
                              "-F", f"name={name}", "-F", f"number={number}", *after,
                              "-f", f"query={QUERY}"], cwd, env))
        pull = data["data"]["repository"]["pullRequest"]
        if first and queue_defers and pull["isMergeQueueEnabled"]:
            raise Deferred("its base branch uses a merge queue")
        first = False
        page = pull["reviewThreads"]
        yield from page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return
        after = ["-f", f"after={page['pageInfo']['endCursor']}"]


def check(args, env, flags, cwd):
    url = gh(["pr", "view", *args, "--json", "url", "-q", ".url"], cwd, env).strip()
    try:
        if flags["auto"]:
            raise Deferred("--auto was passed")
        # --admin merges at once, skipping the queue.
        found = threads(url, cwd, env, queue_defers=not flags["admin"])
        open_threads = [summary(t) for t in found if not t["isResolved"]]
    except Deferred as reason:
        return [f"Merge blocked: {url} would land later ({reason}), after this check runs, "
                "so a thread opened before then would land unseen.",
                "Wait for the required checks, resolve every thread, then merge directly."]
    if open_threads:
        return [f"Merge blocked: {url} has {len(open_threads)} unresolved review thread(s):",
                *open_threads,
                "Triage each one: fix it or reply with why not, then resolve the thread. "
                "Rerun the merge only when none are open."]
    return []


def main():
    try:
        event = json.load(sys.stdin)
        command = event["tool_input"]["command"]
        cwd = os.fspath(event["cwd"])
        found = list(merges(command))
    except (KeyError, TypeError, ValueError) as error:
        print(f"Merge blocked: could not check the command ({error}).", file=sys.stderr)
        return 2
    for args, env, flags in found:
        try:
            problems = check(args, env, flags, cwd)
        except (RuntimeError, OSError, subprocess.TimeoutExpired, KeyError, TypeError, ValueError) as error:
            problems = ["Merge blocked: could not read the PR's review threads.", str(error)]
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

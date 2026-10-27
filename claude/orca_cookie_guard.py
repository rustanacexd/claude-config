#!/usr/bin/env python3
"""Claude Code PreToolUse hook: refuse a command that wipes Orca's cookie jar.

`orca cookie delete` and `orca cookie clear` clear every Orca cookie, Google sign-ins
included, so the user must sign in again with 2FA. On 2026-10-26 an agent's capture
script did this four times. A command is refused when `cookie` is the subcommand of a
command, as in `orca cookie delete` or a wrapper `o cookie clear`. A search such as
`grep "orca cookie delete" AGENTS.md` passes, because there `cookie` is inside an argument.
"""

import json
import re
import shlex
import sys

WIPES = {"delete", "clear", "remove", "rm"}
SEPARATORS = "();<>|&{}\n"
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")


def commands(text):
    lexer = shlex.shlex(text.replace("\\\n", " "), posix=True, punctuation_chars=SEPARATORS)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    words = []
    try:
        for token in lexer:
            if all(char in SEPARATORS for char in token):
                yield words
                words = []
            else:
                words.append(token)
    except ValueError:
        pass
    yield words


def wipes_cookies(text):
    for words in commands(text):
        while words and ASSIGNMENT.fullmatch(words[0]):
            words = words[1:]
        if len(words) >= 3 and words[1].lower() in ("cookie", "cookies") and words[2].lower() in WIPES:
            return True
    return False


if __name__ == "__main__":
    payload = json.load(sys.stdin)
    command = str((payload.get("tool_input") or {}).get("command", ""))
    if wipes_cookies(command):
        print(
            "Blocked: `orca cookie delete/clear` wipes every Orca cookie, Google sign-in included, "
            "and the user must sign in again with 2FA. Sign in for tests with server-side sessions instead.",
            file=sys.stderr,
        )
        sys.exit(2)

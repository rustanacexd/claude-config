"""Entry point for every hook event. Exits 0 or 2, never 1: Claude Code treats exit 1 as a non-blocking error and
runs the call, so a crash on PreToolUse or TaskCompleted must become a block. A crash on Stop or SessionStart
allows instead, because a Stop gate that always crashed would keep every session from ending."""

from __future__ import annotations

import sys

NEVER_BLOCK_ON_CRASH = ("Stop", "SessionStart")


def gates():
    # Imported here so that an import or syntax error on an older Python reaches main's handler.
    from g1_merge import GATE as G1
    from g2_pr import GATE as G2
    from g6_mandate import GATE as G6

    return (G1, G2, G6)


def applies(gate, hook) -> bool:
    """Each trigger literal is a shell `case` pattern that gate.sh tests as `*<literal>*`, so a `*` inside one matches
    anything and a literal without one is a substring test."""
    from core import Event
    from fnmatch import fnmatchcase

    if gate.event is not hook.event:
        return False
    if hook.event is not Event.PRE_TOOL_USE:
        return True
    if hook.tool_name not in gate.tools:
        return False
    return gate.trigger_literals is None or any(fnmatchcase(hook.command, f"*{lit}*") for lit in gate.trigger_literals)


def run(raw: str, env):
    from core import ALLOW, parse_hook_call, render
    from evidence import Transcripts

    hook = parse_hook_call(raw)
    active = [g for g in gates() if applies(g, hook)]
    if not active:
        return ALLOW
    transcripts = Transcripts(hook)
    decisions = []
    for gate in active:
        subjects = gate.subjects(hook)
        if subjects:
            decisions.extend(gate.decide(subjects, transcripts, env))
    if decisions and env.log_path:
        _log(env.log_path, env, hook, decisions)
    return render(hook.event, decisions, env)


def _log(path, env, hook, decisions) -> None:
    import json
    from datetime import datetime, timezone

    row = {
        "at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "event": hook.event.value,
        "modes": {d.gate: env.mode_for(d.gate).value for d in decisions},
        "session": hook.session_id,
        "agent": hook.agent_id,
        "subjects": [f"{d.gate} {d.subject}" for d in decisions],
        "failed": sorted(r for d in decisions for r in d.failed_ids),
        "advisory": sorted(f.req.rid for d in decisions for f in d.advisories),
        "escaped": sorted(e.failure.req.rid for d in decisions for e in d.escaped),
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        pass


def main(stdin, stdout, stderr, environ, event_name: str = "PreToolUse") -> int:
    try:
        from core import Env, Event

        outcome = run(stdin.read(), Env.from_environ(environ, Event(event_name)))
        stdout.write(outcome.stdout)
        stderr.write(outcome.stderr)
        return outcome.exit_code
    except BaseException as exc:
        what = f"The workflow gate crashed ({type(exc).__name__}: {exc})"
        if event_name in NEVER_BLOCK_ON_CRASH:
            import json

            stdout.write(json.dumps({"systemMessage": f"{what}, so it did not check this {event_name}. The bug is in ~/.claude/gates."}))
            return 0
        stderr.write(f"{what}, so it blocked this call. The bug is in ~/.claude/gates, not in your call. Tell the user.\n")
        return 2


if __name__ == "__main__":
    import os

    sys.exit(main(sys.stdin, sys.stdout, sys.stderr, os.environ, *sys.argv[1:2]))

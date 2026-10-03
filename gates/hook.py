"""PreToolUse entry point. Exits 0 or 2, never 1: Claude Code treats exit 1 as a non-blocking error and runs
the command, so any crash must become a block."""

from __future__ import annotations

import sys


def run(raw: str, env):
    # Imported here so that an import or syntax error on an older Python reaches main's handler.
    from core import ALLOW, Loaded, Unavailable, parse_hook_call, render
    from evidence import load_session
    from g1_merge import GATE

    active = [g for g in (GATE,) if g.trigger_literal in raw]
    if not active:
        return ALLOW
    hook = parse_hook_call(raw)

    def load():
        try:
            return load_session(hook.transcript_path, hook.agent_id, hook.tool_use_id)
        except Unavailable:
            raise
        except Exception as exc:
            raise Unavailable(f"could not parse the transcript: {exc!r}", "report this gate bug to the user") from exc

    decisions = []
    session = None
    for gate in active:
        subjects = gate.subjects(hook)
        if subjects:
            session = session or Loaded.of(load)
            decisions.extend(gate.decide(subjects, session, env))
    if decisions and env.log_path:
        _log(env.log_path, env.mode.value, hook, decisions)
    return render(decisions, env.mode)


def _log(path, mode: str, hook, decisions) -> None:
    import json
    from datetime import datetime, timezone

    row = {
        "at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "mode": mode,
        "session": hook.session_id,
        "agent": hook.agent_id,
        "subjects": [d.subject for d in decisions],
        "failed": sorted(r for d in decisions for r in d.failed_ids),
        "escaped": sorted(e.failure.req.rid for d in decisions for e in d.escaped),
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        pass


def main(stdin, stdout, stderr, environ) -> int:
    try:
        from core import Env

        outcome = run(stdin.read(), Env.from_environ(environ))
        stdout.write(outcome.stdout)
        stderr.write(outcome.stderr)
        return outcome.exit_code
    except BaseException as exc:
        stderr.write(
            f"The merge gate crashed ({type(exc).__name__}: {exc}), so it blocked this command. The bug is in "
            "~/.claude/gates, not in your command. Tell the user.\n"
        )
        return 2


if __name__ == "__main__":
    import os

    sys.exit(main(sys.stdin, sys.stdout, sys.stderr, os.environ))

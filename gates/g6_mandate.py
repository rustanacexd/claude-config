from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Tuple

from core import Check, Decision, Env, Event, HookCall, RunFailed, Requirement, Unavailable, adjudicate
from evidence import Invocation, Transcripts, parse_shell

OPENS_PR = (("pr", "create"), ("stack", "submit"))
GIT_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class OpenCall:
    inv: Invocation
    workdir: Path

    @property
    def text(self) -> str:
        return " ".join(["gh", *self.inv.sub, *(w.text for w in self.inv.words)])


def find_opens(hook: HookCall) -> Tuple[OpenCall, ...]:
    return tuple(
        OpenCall(inv, inv.workdir or hook.cwd)
        for inv in parse_shell(hook.command, hook.cwd)
        if inv.tool == "gh" and inv.sub in OPENS_PR and not inv.has("--help", "-h")
    )


@dataclass(frozen=True)
class MandateCtx:
    call: OpenCall
    transcripts: Transcripts
    env: Env


def _git(c: MandateCtx, *args: str) -> str:
    remaining = c.env.deadline.remaining()
    if remaining < 1:
        raise Unavailable("ran out of time before asking git", "open the PR again")
    return c.env.run(["git", *args], c.call.workdir, min(GIT_TIMEOUT_S, remaining))


def _literal(c: MandateCtx, *flags: str):
    w = c.call.inv.value_of(*flags)
    if w is not None and w.dynamic:
        raise Unavailable(f"{flags[0]} {w.text} is a shell expression", f"pass a literal {flags[0]}")
    return w.text if w is not None else None


def changed_files(c: MandateCtx) -> Tuple[str, ...]:
    base = _literal(c, "--base", "-B")
    if base is None:
        try:
            base = _git(c, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip().split("/", 1)[-1] or "main"
        except RunFailed:
            base = "main"
    head = (_literal(c, "--head", "-H") or "HEAD").rsplit(":", 1)[-1]
    try:
        out = _git(c, "diff", "--name-only", f"origin/{base}...{head}")
    except RunFailed:
        try:
            out = _git(c, "diff", "--name-only", f"{base}...{head}")
        except RunFailed as exc:
            raise Unavailable(str(exc), "open the PR from inside its git worktree, or run the poteto-mode skill first") from exc
    return tuple(line for line in out.splitlines() if line.strip())


def check_mandate(c: MandateCtx) -> Check:
    if c.transcripts.poteto_active():
        return Check.passed("poteto-mode is active")
    files = changed_files(c)
    if len(files) <= 1:
        return Check.passed(f"the diff touches {len(files)} file{'' if len(files) == 1 else 's'}")
    shown = ", ".join(files[:3]) + (", ..." if len(files) > 3 else "")
    return Check.failed(
        f"the diff touches {len(files)} files ({shown}) and poteto-mode is not active",
        "run the poteto-mode skill (`pstack:poteto-mode`), follow its Opening a PR playbook, then open the PR again",
    )


R1 = Requirement("G6.R1", "poteto-mode for a multi-file PR", check_mandate)


class MandateGate:
    name = "G6"
    event = Event.PRE_TOOL_USE
    tools = frozenset({"Bash"})
    trigger_literals = ("gh pr create", "gh stack submit")

    def subjects(self, hook: HookCall) -> Tuple[OpenCall, ...]:
        return find_opens(hook)

    def decide(self, subjects: Sequence[OpenCall], transcripts: Transcripts, env: Env) -> Tuple[Decision, ...]:
        escapes = transcripts.escapes()
        return tuple(
            adjudicate(self.name, f"`{call.text}`", (R1,), MandateCtx(call, transcripts, env), escapes) for call in subjects
        )


GATE = MandateGate()

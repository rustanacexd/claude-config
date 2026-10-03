from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from core import Check, Decision, Env, Event, HookCall, Requirement, adjudicate
from evidence import Edited, Invocation, Read, SkillRan, Transcripts, is_scratch, is_todo, parse_shell, skips_hooks

OPENS_PR = (("pr", "create"), ("stack", "submit"))
NOT_POTETO = "poteto-mode is not active in this session"


@dataclass(frozen=True)
class PrCall:
    inv: Invocation

    @property
    def opens_pr(self) -> bool:
        return self.inv.tool == "gh"

    @property
    def text(self) -> str:
        return " ".join([self.inv.tool, *self.inv.sub, *(w.text for w in self.inv.words)])


def find_calls(hook: HookCall) -> Tuple[PrCall, ...]:
    return tuple(
        PrCall(inv)
        for inv in parse_shell(hook.command, hook.cwd)
        if (inv.tool == "gh" and inv.sub in OPENS_PR and not inv.has("--help", "-h")) or skips_hooks(inv)
    )


@dataclass(frozen=True)
class PrCtx:
    call: PrCall
    transcripts: Transcripts


def _skill_after_last_change(c: PrCtx, skill: str) -> Check:
    if not c.transcripts.poteto_active():
        return Check.passed(NOT_POTETO)
    session = c.transcripts.session.get()
    last = session.latest(Edited, lambda e: not (is_scratch(e.path) or is_todo(e.path)))
    if last is None:
        return Check.passed("no edits in this session")
    runs = [(r, ledger) for ledger in session.everyone for r in ledger.of(SkillRan) if r.skill == skill and last.precedes(r, ledger)]
    if runs:
        r, ledger = runs[-1]
        return Check.passed(f"{skill} at {ledger.where(r.stamp)}, after the last edit at {last.where}")
    return Check.failed(
        f"no {skill} run after the last edit, {last.event.path} at {last.where}",
        f"run the {skill} skill with the Skill tool (`pstack:{skill}`) on the diff, then open the PR again",
    )


def check_deslop(c: PrCtx) -> Check:
    return _skill_after_last_change(c, "deslop")


def check_no_comments(c: PrCtx) -> Check:
    return _skill_after_last_change(c, "no-comments")


PROSE_SKILLS = ("technical-writing", "unslop")


def check_prose(c: PrCtx) -> Check:
    if not c.transcripts.poteto_active():
        return Check.passed(NOT_POTETO)
    session = c.transcripts.session.get()
    seen = {
        name
        for ledger in session.everyone
        for name in PROSE_SKILLS
        if any(r.skill == name for r in ledger.of(SkillRan))
        or any(r.complete and f"/{name}/SKILL.md" in r.path for r in ledger.of(Read))
    }
    missing = [n for n in PROSE_SKILLS if n not in seen]
    if not missing:
        return Check.passed("technical-writing and unslop ran")
    return Check.failed(
        f"no run or full read of {' or '.join(missing)} in this session",
        "write the PR title and body with the technical-writing skill, then the unslop skill",
    )


def check_hooks_kept(c: PrCtx) -> Check:
    return Check.failed(
        f"`{c.call.text}` skips the git hooks",
        "drop --no-verify (and commit's -n) and fix what the hook reports. If you must skip them, declare "
        "`skip: G2.R4 <reason>` in a task first",
    )


R1 = Requirement("G2.R1", "deslop after the last edit", check_deslop)
R2 = Requirement("G2.R2", "no-comments after the last edit", check_no_comments)
R3 = Requirement("G2.R3", "PR prose ran technical-writing and unslop", check_prose, advisory=True)
R4 = Requirement("G2.R4", "git hooks not skipped", check_hooks_kept)


class PrGate:
    name = "G2"
    event = Event.PRE_TOOL_USE
    tools = frozenset({"Bash"})
    trigger_literals = ("gh pr create", "gh stack submit", "git commit", "git push", "--no-verify")

    def subjects(self, hook: HookCall) -> Tuple[PrCall, ...]:
        return find_calls(hook)

    def decide(self, subjects: Sequence[PrCall], transcripts: Transcripts, env: Env) -> Tuple[Decision, ...]:
        escapes = transcripts.escapes()
        return tuple(
            adjudicate(self.name, f"`{call.text}`", (R1, R2, R3) if call.opens_pr else (R4,), PrCtx(call, transcripts), escapes)
            for call in subjects
        )


GATE = PrGate()

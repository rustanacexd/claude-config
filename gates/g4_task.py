from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence, Tuple

from core import Check, Decision, Env, Event, HookCall, Requirement, adjudicate
from evidence import SkillRan, Transcripts

ROUTED_SKILLS = (
    "deslop", "no-comments", "technical-writing", "unslop", "architect", "arena", "swarm", "interrogate",
    "show-me-your-work", "figure-it-out", "tdd",
)
COMMON_WORD_SKILLS = ("how", "why")


def _named(skill: str) -> re.Pattern:
    if skill in COMMON_WORD_SKILLS:
        return re.compile(rf"(?<![\w-])(?:/{skill}|pstack:{skill}|{skill} skill)(?![\w-])", re.I)
    return re.compile(rf"(?<![\w-]){re.escape(skill)}(?![\w-])", re.I)


SKILL_PATTERNS = tuple((skill, _named(skill)) for skill in ROUTED_SKILLS + COMMON_WORD_SKILLS)


def named_skills(text: str) -> Tuple[str, ...]:
    return tuple(skill for skill, pattern in SKILL_PATTERNS if pattern.search(text))


@dataclass(frozen=True)
class TaskCtx:
    hook: HookCall
    transcripts: Transcripts

    @property
    def text(self) -> str:
        return f"{self.hook.task_subject}\n{self.hook.task_description}"


def check_skills_ran(c: TaskCtx) -> Check:
    if "skip:" in c.text:
        return Check.passed("the task declares a skip")
    named = named_skills(c.text)
    if not named:
        return Check.passed("the task names no routed skill")
    if not c.transcripts.poteto_active():
        return Check.passed("poteto-mode is not active in this session")
    ran = {r.skill for ledger in c.transcripts.session.get().everyone for r in ledger.of(SkillRan)}
    missing = [s for s in named if s not in ran]
    if not missing:
        return Check.passed(f"{', '.join(named)} ran in this session")
    return Check.failed(
        f"task #{c.hook.task_id} names {', '.join(missing)}, but no Skill call ran {'it' if len(missing) == 1 else 'them'} "
        "in this session or its subagents",
        f"run {' and '.join(f'`pstack:{s}`' for s in missing)} with the Skill tool, then complete the task again. If the "
        "step does not apply, add `skip: <reason>` to the task description first",
    )


R1 = Requirement("G4.R1", "a task that names a skill ran it", check_skills_ran)


class TaskGate:
    name = "G4"
    event = Event.TASK_COMPLETED
    tools = frozenset()
    trigger_literals = None

    def subjects(self, hook: HookCall) -> Tuple[HookCall, ...]:
        return (hook,)

    def decide(self, subjects: Sequence[HookCall], transcripts: Transcripts, env: Env) -> Tuple[Decision, ...]:
        escapes = transcripts.escapes()
        return tuple(adjudicate(self.name, f"completing task #{h.task_id} {h.task_subject!r}", (R1,), TaskCtx(h, transcripts), escapes)
                     for h in subjects)


GATE = TaskGate()

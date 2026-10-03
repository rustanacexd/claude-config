from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from core import Check, Decision, Env, Event, HookCall, Requirement, adjudicate
from evidence import SkillRan, Spawned, Transcripts, skill_name, subagent_path

FAN_OUT_SKILLS = ("swarm", "arena", "architect", "interrogate")
SIBLING_LIMIT = 2
ASSISTANT = re.compile(r'"type":\s*"assistant"')
NOT_POTETO = "poteto-mode is not active in this session"


def current_msg_id(hook: HookCall) -> Optional[str]:
    path = subagent_path(hook.transcript_path, hook.agent_id) if hook.agent_id else hook.transcript_path
    own = re.compile(r'"id":\s*"%s"' % re.escape(hook.tool_use_id or ""))
    newest = None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if not ASSISTANT.search(line):
                    continue
                msg_id = (json.loads(line).get("message") or {}).get("id")
                if hook.tool_use_id and own.search(line):
                    return msg_id
                newest = msg_id or newest
    except (OSError, ValueError):
        return None
    return newest


@dataclass(frozen=True)
class RoutingCtx:
    hook: HookCall
    transcripts: Transcripts


def check_fan_out(c: RoutingCtx) -> Check:
    if c.hook.tool_name != "Agent":
        return Check.passed("not an Agent call")
    if not c.transcripts.poteto_active():
        return Check.passed(NOT_POTETO)
    s = c.transcripts.session.get()
    ran = [r.skill for ledger in s.ledgers for r in ledger.of(SkillRan) if r.skill in FAN_OUT_SKILLS]
    if ran:
        return Check.passed(f"{ran[-1]} ran in this session")
    msg_id = current_msg_id(c.hook)
    siblings = [e for e in s.actor.of(Spawned) if msg_id and e.stamp.msg_id == msg_id]
    if len(siblings) < SIBLING_LIMIT:
        return Check.passed(f"{len(siblings)} earlier Agent call{'s' if len(siblings) != 1 else ''} in this message")
    return Check.failed(
        f"this is Agent call {len(siblings) + 1} in one message, and no {', '.join(FAN_OUT_SKILLS)} skill ran",
        "fan out through the swarm skill (coverage, races, exploration) or arena (competing designs), which own the "
        "partition, models and merge",
    )


def check_babysit(c: RoutingCtx) -> Check:
    if c.hook.tool_name != "Skill" or skill_name(str(c.hook.tool_input.get("skill") or "")) != "babysit":
        return Check.passed("not the babysit skill")
    if not c.transcripts.poteto_active():
        return Check.passed(NOT_POTETO)
    return Check.failed(
        "poteto-mode routes PR-status requests to its Babysit playbook, not the bundled babysit skill",
        "read playbooks/babysit.md in the poteto-mode skill directory in full and follow it",
    )


R1 = Requirement("G5.R1", "parallel fan-out goes through swarm or arena", check_fan_out, advisory=True)
R2 = Requirement("G5.R2", "babysit goes through the playbook", check_babysit)


class RoutingGate:
    name = "G5"
    event = Event.PRE_TOOL_USE
    tools = frozenset({"Agent", "Skill"})
    trigger_literals = None

    def subjects(self, hook: HookCall) -> Tuple[HookCall, ...]:
        return (hook,)

    def decide(self, subjects: Sequence[HookCall], transcripts: Transcripts, env: Env) -> Tuple[Decision, ...]:
        escapes = transcripts.escapes()
        return tuple(adjudicate(self.name, f"{h.tool_name} call", (R1, R2), RoutingCtx(h, transcripts), escapes) for h in subjects)


GATE = RoutingGate()

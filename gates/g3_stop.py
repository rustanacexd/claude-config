from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from core import Check, Decision, Env, Event, HookCall, Requirement, Unavailable, adjudicate
from evidence import (
    Advised, AppControl, Committed, Edited, Human, Placed, Pushed, Read, Session, SkillRan, TaskOp,
    Tested, Transcripts, is_scratch, is_todo,
)

PLAYBOOK = re.compile(r"skills/poteto-mode/playbooks/[^/]+\.md$")
STEP = re.compile(r"^(\d+)\. (.+)$", re.M)
PRINCIPLE = re.compile(r"\*\*([^*]+)\*\* \(\*\*(principle-[a-z0-9-]+)\*\*\)")
POTETO_SKILL_GLOB = (Path.home() / ".claude/plugins/cache/pstack-claude/pstack", "*/skills/poteto-mode/SKILL.md")
DONE_CLAIM = re.compile(r"\b(done|ready for review|landed|merged|fixed|completed?)\b", re.I)
NEGATED = re.compile(r"(n't|\b(not|never|no)\b)[^.!?\n]{0,30}$", re.I)
STEP_PREFIX = 40


@dataclass(frozen=True)
class StopCtx:
    hook: HookCall
    transcripts: Transcripts

    @property
    def session(self) -> Session:
        return self.transcripts.session.get()


def _activation(s: Session, first: bool = False) -> Optional[Placed]:
    runs = [r for r in s.root.of(SkillRan) if r.skill == "poteto-mode"]
    return Placed(runs[0 if first else -1], s.root) if runs else None


def _after(start: Optional[Placed], s: Session, kinds: Sequence[type], keep=lambda e: True) -> List[Placed]:
    return [
        Placed(e, ledger)
        for ledger in s.everyone
        for kind in kinds
        for e in ledger.of(kind)
        if keep(e) and (start is None or start.precedes(e, ledger))
    ]


def _newest(placed: Iterable[Placed]) -> Optional[Placed]:
    return max(placed, key=lambda p: p.event.stamp.at, default=None)


def _counts_as_change(e) -> bool:
    return not isinstance(e, Edited) or not (is_scratch(e.path) or is_todo(e.path))


def _turn_start(s: Session) -> Optional[Placed]:
    human = s.root.last(Human)
    return Placed(human, s.root) if human else None


def check_todolist(c: StopCtx) -> Check:
    s = c.session
    start = _activation(s)
    ops = _after(start, s, (TaskOp,))
    if ops:
        return Check.passed(f"task or todo write at {ops[0].where}")
    where = f" after poteto-mode ran at {start.where}" if start else ""
    return Check.failed(
        f"no TaskCreate, TaskUpdate, TodoWrite or *todo*.md write{where}",
        "open a todolist whose first items are the matched playbook's steps, copied verbatim. Without TaskCreate or "
        "TodoWrite, write it to a todo.md file",
    )


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*`]", "", text)).strip().lower()


def _skipped(n: str, lines: Sequence[str]) -> bool:
    step = re.compile(rf"(?<![\d.]){n}\.(?!\d)|\bstep {n}\b")
    return any("skip:" in line and step.search(line) for line in lines)


def check_verbatim_steps(c: StopCtx) -> Check:
    s = c.session
    start = _activation(s, first=True)
    reads = [r for r in s.root.of(Read) if r.complete and PLAYBOOK.search(r.path) and (start is None or start.precedes(r, s.root))]
    lines = [_norm(line) for t in s.root.of(TaskOp) for line in t.lines]
    text = "\n".join(lines)
    missing, gone = [], []
    for path in dict.fromkeys(r.path for r in reads):
        try:
            body = Path(path).read_text(encoding="utf-8")
        except OSError:
            gone.append(path)
            continue
        absent = [n for n, step in STEP.findall(body) if _norm(step)[:STEP_PREFIX] not in text and not _skipped(n, lines)]
        if absent:
            missing.append(f"{Path(path).name} steps {', '.join(absent)}")
    gone_note = f" ({len(gone)} playbook file{'s' if len(gone) > 1 else ''} no longer on disk)" if gone else ""
    if missing:
        return Check.failed(
            f"{'; '.join(missing)} are not in the todolist{gone_note}",
            "copy each step of every playbook you follow into the todolist verbatim, or mark it `skip: <reason>`",
        )
    return Check.passed(f"{len(reads)} playbook read{'s' if len(reads) != 1 else ''} copied{gone_note}")


def _poteto_skill_md(s: Session) -> Optional[Path]:
    reads = [r.path for r in s.root.of(Read) if r.path.endswith("poteto-mode/SKILL.md")]
    if reads and Path(reads[-1]).is_file():
        return Path(reads[-1])
    root, pattern = POTETO_SKILL_GLOB
    return max(root.glob(pattern), key=lambda p: p.stat().st_mtime, default=None)


def check_principles_read(c: StopCtx) -> Check:
    reply = c.hook.last_assistant_message
    s = c.session
    skill_md = _poteto_skill_md(s)
    if skill_md is None:
        return Check.passed("no poteto-mode SKILL.md on disk to read the Principles index from")
    index = PRINCIPLE.findall(skill_md.read_text(encoding="utf-8"))
    cited = {slug: name for name, slug in index if re.search(rf"\b{re.escape(name)}\b", reply) or slug in reply}
    read = {r.path for r in s.root.of(Read) if r.complete} | {f"{r.skill}/SKILL.md" for r in s.root.of(SkillRan)}
    unread = [f"{name} ({slug})" for slug, name in cited.items() if not any(f"{slug}/SKILL.md" in p for p in read)]
    if unread:
        return Check.failed(
            f"the reply cites {', '.join(unread)} without a full read of that principle's SKILL.md in this session",
            "read each cited principle's SKILL.md in full, or drop the citation from the reply",
        )
    return Check.passed(f"{len(cited)} cited principle{'s' if len(cited) != 1 else ''}, each read")


def _describe(change) -> str:
    return f"the edit of {change.path}" if isinstance(change, Edited) else {Committed: "a commit", Pushed: "a push"}[type(change)]


def check_advisor(c: StopCtx) -> Check:
    s = c.session
    last = _newest(_after(_turn_start(s), s, (Edited, Committed, Pushed), _counts_as_change))
    if last is None:
        return Check.passed("this turn made no edit, commit or push")
    advised = [a for a in s.root.of(Advised) if last.precedes(a, s.root)]
    if advised:
        return Check.passed(f"advisor at {s.root.where(advised[-1].stamp)}, after the last change at {last.where}")
    return Check.failed(
        f"no advisor call after this turn's last change, {_describe(last.event)} at {last.where}",
        "call advisor now that the work is durable, then give the final answer",
    )


def _claims_done(reply: str) -> Optional[str]:
    for m in DONE_CLAIM.finditer(reply):
        sentence = re.split(r"[.!?\n]", reply[: m.start()])[-1]
        if not NEGATED.search(sentence):
            return m.group(0)
    return None


def check_done_claim(c: StopCtx) -> Check:
    claim = _claims_done(c.hook.last_assistant_message)
    if claim is None:
        return Check.passed("the reply makes no done claim")
    s = c.session
    start = _turn_start(s)
    edit = _newest(_after(start, s, (Edited,), _counts_as_change))
    if edit is None:
        return Check.passed(f"the reply says {claim!r} and this turn edited nothing")
    tested = _newest(_after(start, s, (Tested,)))
    if tested is not None and edit.precedes(tested.event, tested.ledger):
        return Check.passed(f"tests ran at {tested.where}, after the last edit at {edit.where}")
    return Check.failed(
        f"the reply says {claim!r}, but {edit.event.path} was edited at {edit.where} after this turn's last test run",
        "run the tests or the verify script on the final code before you claim it is done",
    )


def check_teardown(c: StopCtx) -> Check:
    s = c.session
    up = _newest(Placed(e, ledger) for ledger in s.everyone for e in ledger.of(AppControl) if e.up)
    if up is None:
        return Check.passed("no app session was brought up")
    app = up.event.app
    downs = [p for p in _after(up, s, (AppControl,)) if p.event.app == app and not p.event.up]
    if downs:
        return Check.passed(f"{app.script} {app.up} at {up.where} came down at {downs[0].where}")
    return Check.failed(
        f"{app.script} {app.up} at {up.where} has no later {app.down}",
        f"bring the session down with `{app.tool} run {app.script} -- {app.down}` before you stop",
    )


R1 = Requirement("G3.R1", "todolist opened after poteto-mode", check_todolist)
R2 = Requirement("G3.R2", "playbook steps copied verbatim", check_verbatim_steps, advisory=True)
R3 = Requirement("G3.R3", "cited principles were read", check_principles_read)
R4 = Requirement("G3.R4", "advisor after this turn's last change", check_advisor)
R5 = Requirement("G3.R5", "done claim backed by a later test run", check_done_claim, advisory=True)
R6 = Requirement("G3.R6", "app session brought down", check_teardown, advisory=True)


def poteto_active_failing_open(transcripts: Transcripts) -> bool:
    try:
        return transcripts.poteto_active()
    except Unavailable:
        return False


class StopGate:
    name = "G3"
    event = Event.STOP
    tools = frozenset()
    trigger_literals = None

    def subjects(self, hook: HookCall) -> Tuple[HookCall, ...]:
        return () if hook.agent_id else (hook,)

    def decide(self, subjects: Sequence[HookCall], transcripts: Transcripts, env: Env) -> Tuple[Decision, ...]:
        if not poteto_active_failing_open(transcripts):
            return ()
        escapes = transcripts.escapes()
        return tuple(adjudicate(self.name, "end of turn", (R1, R2, R3, R4, R5, R6), StopCtx(h, transcripts), escapes) for h in subjects)


GATE = StopGate()

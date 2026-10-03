from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from core import Decision, Env, Event, HookCall
from evidence import Edited, Read, Session, TaskOp, Transcripts, is_todo
from g3_stop import PLAYBOOK, poteto_active_failing_open

CAP = 2000
CLOSED = ("completed", "deleted")
HEADER = (
    "poteto-mode state from before this compaction (G7). Compaction dropped the text of every playbook and skill "
    "read so far. Re-read each playbook below in full before you follow it again. G1 accepts only a full read of "
    "playbooks/shipping.md made after this compaction."
)


def open_tasks(ops: Sequence[TaskOp]) -> List[str]:
    tasks: Dict[str, str] = {}
    todos: List[TaskOp] = []
    for n, op in enumerate(ops):
        if op.tool == "TaskCreate":
            tasks[op.task_id or f"unnumbered {n}"] = op.subject
        elif op.tool == "TaskUpdate" and op.task_id in tasks:
            if op.status in CLOSED:
                del tasks[op.task_id]
            elif op.subject:
                tasks[op.task_id] = op.subject
        elif op.tool == "TodoWrite":
            todos = [t for t in todos if t.stamp == op.stamp] + [op]
    listed = [f"#{k} {v}" if not k.startswith("unnumbered") else v for k, v in tasks.items()]
    return listed + [t.subject for t in todos if t.status not in CLOSED]


def reinject(s: Session) -> str:
    root = s.root
    sections: List[Tuple[str, List[str]]] = [
        ("Playbooks read:", list(dict.fromkeys(r.path for r in root.of(Read) if PLAYBOOK.search(r.path)))),
        ("Open tasks:", open_tasks(root.of(TaskOp))),
        ("Todo files:", list(dict.fromkeys(e.path for e in root.of(Edited) if is_todo(e.path)))),
        ("Declared skips:", list(dict.fromkeys(line.strip() for t in root.of(TaskOp) for line in t.lines if "skip:" in line))),
    ]
    text = "\n".join([HEADER, *(f"{title}\n" + "\n".join(f"- {i}" for i in items) for title, items in sections if items)])
    if len(text) <= CAP:
        return text
    marker = f"\n- ... cut at {CAP} characters"
    return text[: text.rfind("\n", 0, CAP - len(marker))] + marker


class CompactGate:
    name = "G7"
    event = Event.SESSION_START
    tools = frozenset()
    trigger_literals = None

    def subjects(self, hook: HookCall) -> Tuple[HookCall, ...]:
        return (hook,) if hook.source == "compact" else ()

    def decide(self, subjects: Sequence[HookCall], transcripts: Transcripts, env: Env) -> Tuple[Decision, ...]:
        if not poteto_active_failing_open(transcripts):
            return ()
        return (Decision(self.name, "compaction", (), reinject(transcripts.session.get())),)


GATE = CompactGate()

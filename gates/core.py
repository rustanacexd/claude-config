from __future__ import annotations

import enum
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Generic, Iterable, Mapping, Optional, Protocol, Sequence, Tuple, TypeVar, Union

T = TypeVar("T")
C = TypeVar("C")

EXIT_ALLOW = 0
EXIT_BLOCK = 2


class Event(enum.Enum):
    PRE_TOOL_USE = "PreToolUse"
    STOP = "Stop"
    TASK_COMPLETED = "TaskCompleted"
    SESSION_START = "SessionStart"


# Each sits below its settings timeout (60 s, 10 s), because a timed-out hook allows the call.
BUDGET_S = {Event.PRE_TOOL_USE: 40.0, Event.TASK_COMPLETED: 40.0, Event.STOP: 7.0, Event.SESSION_START: 7.0}


class Unavailable(Exception):
    def __init__(self, reason: str, remedy: str = "") -> None:
        super().__init__(reason)
        self.remedy = remedy


class RunFailed(Unavailable):
    pass


Runner = Callable[[Sequence[str], Path, float], str]


def subprocess_runner(argv: Sequence[str], cwd: Path, timeout: float) -> str:
    try:
        proc = subprocess.run(
            list(argv),
            cwd=str(cwd) if cwd.is_dir() else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RunFailed(f"`{' '.join(argv[:3])}` timed out after {timeout:.0f}s") from None
    except OSError as exc:
        raise RunFailed(f"`{argv[0]}` could not run: {exc}") from exc
    if proc.returncode != 0:
        tail = proc.stderr.strip().splitlines()[-1:] or [""]
        raise RunFailed(f"`{' '.join(argv[:3])}` exited {proc.returncode}: {tail[0]}")
    return proc.stdout


@dataclass(frozen=True)
class Deadline:
    expires_at: float

    def remaining(self) -> float:
        return self.expires_at - time.monotonic()


class Mode(enum.Enum):
    BLOCK = "block"
    WARN = "warn"


def _mode(value: Optional[str]) -> Mode:
    return Mode.WARN if value == "warn" else Mode.BLOCK


@dataclass(frozen=True)
class Env:
    run: Runner
    deadline: Deadline
    mode: Mode
    log_path: Optional[Path]
    gate_modes: Mapping[str, Mode] = field(default_factory=dict)
    no_block_reason: Optional[str] = None

    def mode_for(self, gate: str) -> Mode:
        return self.gate_modes.get(gate, self.mode)

    @staticmethod
    def from_environ(environ: Mapping[str, str], event: Event) -> "Env":
        log = environ.get("GATES_LOG")
        return Env(
            run=subprocess_runner,
            deadline=Deadline(time.monotonic() + BUDGET_S[event]),
            mode=_mode(environ.get("GATES_MODE")),
            log_path=Path(log) if log else None,
            gate_modes={k[len("GATES_MODE_"):]: _mode(v) for k, v in environ.items() if k.startswith("GATES_MODE_")},
        )


@dataclass(frozen=True)
class Loaded(Generic[T]):
    value: Optional[T]
    error: Optional[str] = None
    remedy: str = ""

    def get(self) -> T:
        if self.error is not None:
            raise Unavailable(self.error, self.remedy)
        return self.value

    @staticmethod
    def of(load: Callable[[], T]) -> "Loaded[T]":
        try:
            return Loaded(load())
        except Unavailable as exc:
            return Loaded(None, str(exc), exc.remedy)


class MalformedHook(Exception):
    pass


@dataclass(frozen=True)
class HookCall:
    event: Event
    session_id: str
    transcript_path: Path
    cwd: Path
    agent_id: Optional[str] = None
    agent_type: Optional[str] = None
    tool_name: str = ""
    tool_input: Mapping[str, object] = field(default_factory=dict)
    tool_use_id: Optional[str] = None
    stop_hook_active: bool = False
    last_assistant_message: str = ""
    task_id: Optional[str] = None
    task_subject: str = ""
    task_description: str = ""
    source: Optional[str] = None

    @property
    def command(self) -> str:
        return str(self.tool_input.get("command") or "")


def _opt(value: object) -> Optional[str]:
    return None if value is None else str(value)


def parse_hook_call(raw: str) -> HookCall:
    try:
        d = json.loads(raw)
        tool_input = d.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            raise TypeError(f"tool_input is {type(tool_input).__name__}")
        return HookCall(
            event=Event(d["hook_event_name"]),
            session_id=str(d.get("session_id", "")),
            transcript_path=Path(d["transcript_path"]),
            cwd=Path(d.get("cwd") or "."),
            agent_id=_opt(d.get("agent_id")),
            agent_type=_opt(d.get("agent_type")),
            tool_name=str(d.get("tool_name", "")),
            tool_input=tool_input,
            tool_use_id=_opt(d.get("tool_use_id")),
            stop_hook_active=d.get("stop_hook_active") is True,
            last_assistant_message=str(d.get("last_assistant_message") or ""),
            task_id=_opt(d.get("task_id")),
            task_subject=str(d.get("task_subject") or ""),
            task_description=str(d.get("task_description") or ""),
            source=_opt(d.get("source")),
        )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise MalformedHook(f"hook payload is malformed: {exc!r}") from exc


@dataclass(frozen=True)
class Check:
    ok: bool
    detail: str
    remedy: str = ""

    @staticmethod
    def passed(detail: str) -> "Check":
        return Check(True, detail)

    @staticmethod
    def failed(detail: str, remedy: str) -> "Check":
        return Check(False, detail, remedy)


@dataclass(frozen=True)
class Requirement(Generic[C]):
    rid: str
    title: str
    check: Callable[[C], Check]
    escapable: bool = True
    advisory: bool = False


@dataclass(frozen=True)
class Escape:
    rid: str
    reason: str
    source: str


class EscapeLookup(Protocol):
    def get(self, rid: str) -> Optional[Escape]: ...


SKIP_LINE = re.compile(r"^\s*(?:[-*]\s*(?:\[[ xX]\]\s*)?)?skip:\s*(G\d+\.R\d+)\s+(\S.*?)\s*$")


def collect_escapes(lines: Iterable[Tuple[str, str]]) -> Mapping[str, Escape]:
    found = {}
    for text, source in lines:
        m = SKIP_LINE.match(text)
        if m and m.group(1) not in found:
            found[m.group(1)] = Escape(m.group(1), m.group(2), source)
    return found


@dataclass(frozen=True)
class Passed:
    req: Requirement
    detail: str


@dataclass(frozen=True)
class Failed:
    req: Requirement
    detail: str
    remedy: str


@dataclass(frozen=True)
class Escaped:
    failure: Failed
    escape: Escape


Finding = Union[Passed, Failed, Escaped]


@dataclass(frozen=True)
class Decision:
    gate: str
    subject: str
    findings: Tuple[Finding, ...]
    context: str = ""

    @property
    def failed(self) -> Tuple[Failed, ...]:
        return tuple(f for f in self.findings if isinstance(f, Failed) and not f.req.advisory)

    @property
    def advisories(self) -> Tuple[Failed, ...]:
        return tuple(f for f in self.findings if isinstance(f, Failed) and f.req.advisory)

    @property
    def escaped(self) -> Tuple[Escaped, ...]:
        return tuple(f for f in self.findings if isinstance(f, Escaped))

    @property
    def failed_ids(self) -> frozenset:
        return frozenset(f.req.rid for f in self.failed)

    @property
    def blocked(self) -> bool:
        return bool(self.failed)


def adjudicate(
    gate: str, subject: str, requirements: Sequence[Requirement[C]], ctx: C, escapes: EscapeLookup
) -> Decision:
    findings = []
    for req in requirements:
        try:
            chk = req.check(ctx)
        except Unavailable as exc:
            chk = Check.failed(f"cannot verify: {exc}", exc.remedy)
        except Exception as exc:
            chk = Check.failed(f"internal error in this check: {exc!r}", "report this gate bug to the user")
        if chk.ok:
            findings.append(Passed(req, chk.detail))
            continue
        failure = Failed(req, chk.detail, chk.remedy)
        esc = escapes.get(req.rid) if req.escapable else None
        findings.append(Escaped(failure, esc) if esc else failure)
    return Decision(gate, subject, tuple(findings))


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    stdout: str
    stderr: str


ALLOW = Outcome(EXIT_ALLOW, "", "")


def _skip_syntax(blocking: Sequence[Decision]) -> str:
    text = (
        "To skip a requirement you cannot meet, add a task or todo line `skip: <Gn>.<Rn> <reason>`. A line written in "
        "the call just before may not be on disk yet, so if you just wrote it, run the command again as its own call."
    )
    fixed = sorted({f.req.rid for d in blocking for f in d.failed if not f.req.escapable})
    if fixed:
        text += f" {' and '.join(fixed)} cannot be skipped; only its fix above satisfies it."
    return text


def _lines(d: Decision) -> Sequence[str]:
    out = []
    for f in d.findings:
        if isinstance(f, Failed):
            out.append(f"{'ADVISORY' if f.req.advisory else 'FAIL'} {f.req.rid} {f.req.title}: {f.detail}")
            if f.remedy:
                out.append(f"     fix: {f.remedy}")
        elif isinstance(f, Escaped):
            out.append(f"skip {f.failure.req.rid} {f.failure.req.title}: {f.escape.reason} (declared in {f.escape.source})")
        else:
            out.append(f"ok   {f.req.rid} {f.req.title}: {f.detail}")
    return out


def _body(decisions: Sequence[Decision]) -> str:
    return "\n".join(line for d in decisions for line in [f"{d.gate} gate: {d.subject}", *_lines(d), ""])


def _exit0(event: Event, text: str) -> Outcome:
    """additionalContext reaches the model; systemMessage reaches only the user. TaskCompleted has no
    additionalContext, and on Stop it keeps the conversation going like a block, so both use systemMessage."""
    if event in (Event.PRE_TOOL_USE, Event.SESSION_START):
        return Outcome(EXIT_ALLOW, json.dumps({"hookSpecificOutput": {"hookEventName": event.value, "additionalContext": text}}), "")
    return Outcome(EXIT_ALLOW, json.dumps({"systemMessage": text}), "")


def render(event: Event, decisions: Sequence[Decision], env: Env) -> Outcome:
    can_block = event is not Event.SESSION_START and env.no_block_reason is None
    failing = [d for d in decisions if d.blocked]
    blocking = [d for d in failing if can_block and env.mode_for(d.gate) is Mode.BLOCK]
    warned = [d for d in failing if d not in blocking]
    notes = []
    if warned:
        why = env.no_block_reason or "the gate is in warn mode or this event never blocks"
        notes.append(f"This was NOT blocked, because {why}. It would have been:\n{_body(warned)}")
    for d in decisions:
        if d in blocking:
            continue
        notes += [f"ADVISORY {f.req.rid} {f.req.title}: {f.detail}" + (f" Fix: {f.remedy}" if f.remedy else "") for f in d.advisories]
        notes += [f"{e.failure.req.rid} skipped: {e.escape.reason} (declared in {e.escape.source})" for e in d.escaped]
    if blocking:
        tail = "".join(f"\n{n}" for n in notes)
        return Outcome(EXIT_BLOCK, "", f"Blocked by the workflow gates.\n{_body(blocking)}{_skip_syntax(blocking)}\n{tail}")
    lines = [d.context for d in decisions if d.context]
    if notes:
        lines += ["Workflow gates allowed this with notes:", *notes]
    return _exit0(event, "\n".join(lines)) if lines else ALLOW

from __future__ import annotations

import enum
import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generic, Iterable, Mapping, Optional, Sequence, Tuple, TypeVar, Union

T = TypeVar("T")
C = TypeVar("C")

EXIT_ALLOW = 0
EXIT_BLOCK = 2
HOOK_BUDGET_S = 40.0  # below the 60 s settings timeout, because a timed-out hook allows the call


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


@dataclass(frozen=True)
class Env:
    run: Runner
    deadline: Deadline
    mode: Mode
    log_path: Optional[Path]

    @staticmethod
    def from_environ(environ: Mapping[str, str]) -> "Env":
        log = environ.get("GATES_LOG")
        return Env(
            run=subprocess_runner,
            deadline=Deadline(time.monotonic() + HOOK_BUDGET_S),
            mode=Mode.WARN if environ.get("GATES_MODE") == "warn" else Mode.BLOCK,
            log_path=Path(log) if log else None,
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
    session_id: str
    transcript_path: Path
    cwd: Path
    tool_name: str
    command: str
    tool_use_id: Optional[str]
    agent_id: Optional[str]


def parse_hook_call(raw: str) -> HookCall:
    try:
        d = json.loads(raw)
        tool_input = d.get("tool_input") or {}
        return HookCall(
            session_id=str(d.get("session_id", "")),
            transcript_path=Path(d["transcript_path"]),
            cwd=Path(d.get("cwd") or "."),
            tool_name=str(d.get("tool_name", "")),
            command=str(tool_input.get("command") or ""),
            tool_use_id=d.get("tool_use_id"),
            agent_id=d.get("agent_id"),
        )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise MalformedHook(f"hook payload is not a PreToolUse call: {exc!r}") from exc


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


@dataclass(frozen=True)
class Escape:
    rid: str
    reason: str
    source: str


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

    @property
    def failed(self) -> Tuple[Failed, ...]:
        return tuple(f for f in self.findings if isinstance(f, Failed))

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
    gate: str, subject: str, requirements: Sequence[Requirement[C]], ctx: C, escapes: Mapping[str, Escape]
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
SKIP_SYNTAX = (
    "To skip a requirement you cannot meet, add a task or todo line `skip: G1.<Rn> <reason>`. "
    "G1.R6 cannot be skipped: only a user message that asks to merge, land or ship satisfies it."
)


def _lines(d: Decision) -> Sequence[str]:
    out = []
    for f in d.findings:
        if isinstance(f, Failed):
            out.append(f"FAIL {f.req.rid} {f.req.title}: {f.detail}")
            if f.remedy:
                out.append(f"     fix: {f.remedy}")
        elif isinstance(f, Escaped):
            out.append(f"skip {f.failure.req.rid} {f.failure.req.title}: {f.escape.reason} (declared in {f.escape.source})")
        else:
            out.append(f"ok   {f.req.rid} {f.req.title}: {f.detail}")
    return out


def _context(text: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}})


def render(decisions: Sequence[Decision], mode: Mode) -> Outcome:
    """Exit 2 with stderr when blocking. Everything said on exit 0 rides additionalContext, the only exit-0
    channel that reaches the model and the transcript."""
    if not decisions:
        return ALLOW
    blocked = [d for d in decisions if d.blocked]
    if blocked:
        body = "\n".join(
            line for d in blocked for line in [f"{d.gate} merge gate: {d.subject}", *_lines(d), ""]
        )
        if mode is Mode.BLOCK:
            return Outcome(EXIT_BLOCK, "", f"Blocked by the merge gate.\n{body}{SKIP_SYNTAX}\n")
        return Outcome(EXIT_ALLOW, _context(f"GATES_MODE=warn, so this was NOT blocked. It would have been:\n{body}"), "")
    notes = [
        f"{e.failure.req.rid} skipped: {e.escape.reason} (declared in {e.escape.source})"
        for d in decisions
        for e in d.escaped
    ]
    if not notes:
        return ALLOW
    return Outcome(EXIT_ALLOW, _context("Merge gate allowed this merge with notes:\n" + "\n".join(notes)), "")

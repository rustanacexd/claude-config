from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

GATES = Path(__file__).resolve().parent.parent / "gates"
sys.path.insert(0, str(GATES))

from core import Deadline, Env, Mode, Outcome, RunFailed  # noqa: E402

REPO = "example/repo"
PR = 42
HEAD = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"
MERGE_ID = "toolu_merge"


def at(minute: int, second: int = 0) -> str:
    return f"2026-01-01T10:{minute:02d}:{second:02d}.000Z"


def gh_at(minute: int, second: int = 0) -> str:
    return f"2026-01-01T10:{minute:02d}:{second:02d}Z"


class Transcript:
    def __init__(self) -> None:
        self.records: List[dict] = []
        self._n = 0

    def _assistant(self, content: dict, when: str) -> None:
        self.records.append({"type": "assistant", "isSidechain": False, "timestamp": when, "cwd": "/work",
                             "message": {"role": "assistant", "content": [content]}})

    def user(self, text: str, when: str, **extra) -> "Transcript":
        self.records.append({"type": "user", "isSidechain": False, "timestamp": when,
                             "message": {"role": "user", "content": text}, **extra})
        return self

    def tool(self, name: str, inp: dict, when: str, result: Optional[str] = "", *, is_error: bool = False,
             tool_id: Optional[str] = None) -> str:
        self._n += 1
        tid = tool_id or f"toolu_{self._n:04d}"
        self._assistant({"type": "tool_use", "id": tid, "name": name, "input": inp}, when)
        if result is not None:
            self.records.append({"type": "user", "isSidechain": False, "timestamp": when,
                                 "message": {"role": "user", "content": [
                                     {"type": "tool_result", "tool_use_id": tid, "content": result, "is_error": is_error}]}})
        return tid

    def bash(self, command: str, when: str, result: Optional[str] = "", **kw) -> str:
        return self.tool("Bash", {"command": command}, when, result, **kw)

    def advisor(self, when: str) -> "Transcript":
        self._assistant({"type": "server_tool_use", "id": f"srvtoolu_{len(self.records)}", "name": "advisor", "input": {}}, when)
        return self

    def compact(self, when: str) -> "Transcript":
        self.records.append({"type": "system", "subtype": "compact_boundary", "isSidechain": False, "timestamp": when,
                             "content": "Conversation compacted"})
        return self

    def local_compact(self, when: str) -> "Transcript":
        return self.user("<local-command-stdout>Compacted </local-command-stdout>", when)

    def task(self, subject: str, when: str) -> "Transcript":
        self.tool("TaskCreate", {"subject": subject, "description": ""}, when, "Task created")
        return self

    def read(self, path: str, when: str, **inp) -> "Transcript":
        self.tool("Read", {"file_path": path, **inp}, when, "# Shipping\n...")
        return self

    def skill(self, name: str, when: str) -> "Transcript":
        self.tool("Skill", {"skill": name, "args": ""}, when, f"Launching skill: {name}")
        return self

    def slash(self, name: str, when: str, args: str = "") -> "Transcript":
        return self.user(f"<command-message>{name}</command-message>\n<command-name>/{name}</command-name>\n"
                         f"<command-args>{args}</command-args>", when)

    def edit(self, path: str, when: str) -> "Transcript":
        self.tool("Edit", {"file_path": path, "old_string": "a", "new_string": "b"}, when, "The file has been updated.")
        return self

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in self.records))
        return path


def comment(cid: int, when: str, body: str, user: str = "reviewer", updated: Optional[str] = None) -> dict:
    return {"id": cid, "html_url": f"https://github.com/{REPO}/pull/{PR}#issuecomment-{cid}", "user": {"login": user},
            "created_at": when, "updated_at": updated or when, "body": body}


def review(cid: int, when: str, body: str, user: str = "bot[bot]") -> dict:
    return {"id": cid, "html_url": f"https://github.com/{REPO}/pull/{PR}#pullrequestreview-{cid}", "user": {"login": user},
            "submitted_at": when, "body": body, "state": "COMMENTED"}


def inline(cid: int, when: str, body: str, user: str = "bot[bot]") -> dict:
    return {"id": cid, "html_url": f"https://github.com/{REPO}/pull/{PR}#discussion_r{cid}", "user": {"login": user},
            "created_at": when, "updated_at": when, "body": body}


@dataclass(frozen=True)
class Facts:
    head: str = HEAD
    issue: Tuple[dict, ...] = ()
    reviews: Tuple[dict, ...] = ()
    inline: Tuple[dict, ...] = ()
    down: Optional[str] = None
    stack: Tuple[Tuple[int, str], ...] = ((40, "MERGED"), (PR, "OPEN"), (PR + 1, "OPEN"))


class FakeGh:
    def __init__(self, facts: Facts) -> None:
        self.facts = facts
        self.calls: List[Sequence[str]] = []

    def __call__(self, argv: Sequence[str], cwd: Path, timeout: float) -> str:
        self.calls.append(list(argv))
        if self.facts.down:
            raise RunFailed(self.facts.down)
        if list(argv[1:3]) == ["stack", "view"]:
            return json.dumps({"trunk": "main", "branches": [
                {"name": f"b{n}", "isMerged": state == "MERGED", "pr": {"number": n, "url": f"https://github.com/{REPO}/pull/{n}", "state": state}}
                for n, state in self.facts.stack]})
        if list(argv[1:3]) == ["pr", "view"]:
            return json.dumps({"number": PR, "url": f"https://github.com/{REPO}/pull/{PR}", "headRefOid": self.facts.head, "state": "OPEN"})
        path = argv[2]
        for suffix, rows in ((f"issues/{PR}/comments", self.facts.issue), (f"pulls/{PR}/reviews", self.facts.reviews),
                             (f"pulls/{PR}/comments", self.facts.inline)):
            if path.endswith(suffix):
                return json.dumps(list(rows))
        raise AssertionError(f"unexpected gh call {argv}")


def forbidden_runner(argv: Sequence[str], cwd: Path, timeout: float) -> str:
    raise AssertionError(f"gh must not run here: {argv}")


def env(run, mode: Mode = Mode.BLOCK) -> Env:
    return Env(run=run, deadline=Deadline(time.monotonic() + 100), mode=mode, log_path=None)


def payload(transcript: Path, command: str, tool_use_id: str = MERGE_ID, agent_id: Optional[str] = None) -> str:
    d = {"session_id": "sess-1", "transcript_path": str(transcript), "cwd": "/work", "hook_event_name": "PreToolUse",
         "tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": tool_use_id}
    if agent_id:
        d["agent_id"] = agent_id
        d["agent_type"] = "general-purpose"
    return json.dumps(d)


def merge_command(pin: str = HEAD) -> str:
    return f"gh pr merge {PR} --repo {REPO} --squash --match-head-commit {pin}"


PASS_BODY = f"**Independent verification: PASS** on `{HEAD}`"
BOT_ID, PASS_ID, REVIEW_ID = 1000000001, 1000000002, 2000000001

GREEN_FACTS = Facts(
    issue=(comment(BOT_ID, gh_at(3), "Codex review: no major issues", user="bot[bot]"), comment(PASS_ID, gh_at(4), PASS_BODY)),
    reviews=(review(REVIEW_ID, gh_at(3, 30), "Looks fine overall"),),
)

Piece = Callable[[Transcript], None]
GREEN_PIECES: Tuple[Tuple[str, Piece], ...] = (
    ("user", lambda t: t.user("please land PR 42 once it is verified", at(0))),
    ("playbook", lambda t: t.read("/plugins/poteto-mode/playbooks/shipping.md", at(1))),
    ("push", lambda t: t.bash("git push origin feat", at(2))),
    ("advisor", lambda t: t.advisor(at(5))),
    ("read_comments", lambda t: t.bash(f"gh pr view {PR} --comments", at(6), "comments..."))
)


@dataclass(frozen=True)
class Case:
    pieces: Tuple[Tuple[str, Piece], ...] = GREEN_PIECES
    facts: Facts = GREEN_FACTS
    command: str = field(default_factory=merge_command)
    delete_transcript: bool = False


def run_case(case: Case, tmp: Path, mode: Mode = Mode.BLOCK) -> Tuple[Outcome, FakeGh]:
    t = Transcript()
    for _, piece in sorted(case.pieces, key=lambda p: _first_time(p[1])):
        piece(t)
    t.bash(case.command, at(7), None, tool_id=MERGE_ID)
    path = t.write(tmp / "session.jsonl")
    if case.delete_transcript:
        path.unlink()
    import hook

    gh = FakeGh(case.facts)
    return hook.run(payload(path, case.command), env(gh, mode)), gh


def _first_time(piece: Piece) -> str:
    probe = Transcript()
    piece(probe)
    return probe.records[0]["timestamp"]


def without(case, *names: str):
    return replace(case, pieces=tuple(p for p in case.pieces if p[0] not in names))


def plus(case, *pieces: Tuple[str, Piece]):
    return replace(case, pieces=case.pieces + pieces)


def failed_ids(outcome: Outcome) -> frozenset:
    return frozenset(line.split()[1] for line in outcome.stderr.splitlines() if line.startswith("FAIL "))


def said(outcome: Outcome) -> str:
    if outcome.stderr or not outcome.stdout:
        return outcome.stderr
    out = json.loads(outcome.stdout)
    return out.get("systemMessage") or out["hookSpecificOutput"]["additionalContext"]


def flagged_ids(outcome: Outcome) -> frozenset:
    return frozenset(line.split()[1] for line in said(outcome).splitlines() if line.startswith(("FAIL ", "ADVISORY ")))

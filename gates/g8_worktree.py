from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Iterator, Optional, Sequence, Tuple

from core import Check, Decision, Env, Event, HookCall, Requirement, adjudicate
from evidence import Invocation, Messaged, Pgrep, SkillRan, Spawned, Transcripts, git_root, parse_shell, written

GIT_WRITES = frozenset({"commit", "reset", "checkout", "rebase", "stash", "clean", "merge", "push"})
FILE_TOOLS = frozenset({"Edit", "Write", "MultiEdit"})
SETTINGS = "*settings*.json"
AGENT_CALL = '"Agent"'
HOME = Path.home()


def linked_worktree(path: Path) -> Optional[Path]:
    for d in (path, *path.parents):
        dot_git = d / ".git"
        if dot_git.is_file():
            return d
        if dot_git.exists():
            return None
    return None


def spellings(root: Path) -> FrozenSet[str]:
    forms = {str(root), os.path.realpath(root)}
    forms |= {f[len("/private"):] for f in list(forms) if f.startswith("/private/")}
    forms |= {"~" + f[len(str(HOME)):] for f in list(forms) if f.startswith(str(HOME) + "/")}
    return frozenset(forms)


def mentions(text: str, forms: FrozenSet[str]) -> bool:
    return any(re.search(r"(?<![\w.-])" + re.escape(f) + r"(?![\w-]|\.\w)", text) for f in forms if f in text)


def is_settings(path: Path) -> bool:
    if not fnmatch.fnmatch(path.name, SETTINGS):
        return False
    live = HOME / ".claude" / path.name
    return "/.claude/" in str(path) or (live.exists() and os.path.realpath(live) == os.path.realpath(path))


@dataclass(frozen=True)
class Target:
    path: Path
    via: str
    foreign: Optional[Path]
    settings: bool


def _absolute(text: str, workdir: Optional[Path]) -> Optional[Path]:
    p = Path(os.path.expanduser(text))
    if p.is_absolute():
        return Path(os.path.normpath(p))
    return Path(os.path.normpath(workdir / p)) if workdir is not None else None


def _bash_paths(inv: Invocation, cwd: Path) -> Iterator[Tuple[Path, str]]:
    workdir = Path(os.path.normpath(inv.workdir or cwd))
    if inv.tool == "git" and inv.sub and inv.sub[0] in GIT_WRITES:
        yield workdir, f"git {inv.sub[0]}"
        return
    removed = [w.text for w in inv.positional(frozenset()) if not w.dynamic] if inv.tool == "rm" else []
    for text in [*removed, *map(str, written(inv))]:
        p = _absolute(text, workdir)
        if p is not None:
            yield p, inv.tool


def _target(path: Path, via: str, cwd: Path) -> Optional[Target]:
    root = linked_worktree(path)
    if root is not None:
        here = git_root(str(cwd))
        if here is not None and os.path.realpath(here) == os.path.realpath(root):
            root = None
    settings = is_settings(path)
    if root is None and not settings:
        return None
    return Target(path, via, root, settings)


def find_targets(hook: HookCall) -> Tuple[Target, ...]:
    if hook.tool_name in FILE_TOOLS:
        raw = str(hook.tool_input.get("file_path") or "")
        found = [(_absolute(raw, hook.cwd), hook.tool_name)] if raw else []
    else:
        found = [pv for inv in parse_shell(hook.command, hook.cwd) for pv in _bash_paths(inv, hook.cwd)]
    targets = (_target(p, via, hook.cwd) for p, via in found if p is not None)
    return tuple(dict.fromkeys(t for t in targets if t is not None))


@dataclass(frozen=True)
class WorktreeCtx:
    hook: HookCall
    target: Target
    transcripts: Transcripts


def check_pgrep(c: WorktreeCtx) -> Check:
    root = c.target.foreign
    if root is None:
        return Check.passed("the target is in this session's own worktree or in no linked worktree")
    if c.hook.agent_id:
        return Check.passed("a subagent's call; the rule covers the main agent")
    forms = spellings(root)
    raw = _text(c.hook.transcript_path)
    if raw is not None and not any(AGENT_CALL in line and f in line for line in raw.splitlines() for f in forms):
        return Check.passed(f"no agent in this session was handed {root}")
    s = c.transcripts.session.get()
    spawns = [e for e in s.root.of(Spawned) if mentions(e.prompt, forms)]
    if not spawns:
        return Check.passed(f"no agent in this session was handed {root}")
    holders = {e.agent_id for e in spawns if e.agent_id}
    resumes = [m for m in s.root.of(Messaged) if m.to in holders or m.resumed in holders]
    latest = max((e.stamp for e in [*spawns, *resumes]), key=lambda st: st.line)
    probes = [p for p in s.root.of(Pgrep) if p.stamp.line > latest.line and mentions(" ".join(p.args), forms)]
    if probes:
        return Check.passed(f"pgrep at {s.root.where(probes[-1].stamp)} after the agent was last handed {root}")
    kind = "messaged" if resumes and latest == resumes[-1].stamp else "spawned"
    return Check.failed(
        f"{c.target.via} writes into {root}, which an agent {kind} at {s.root.where(latest)} was handed, and no pgrep "
        "for that path ran after it",
        f"run `pgrep -fl {root}` as its own Bash call first. If anything but the search answers, the agent still holds "
        "the worktree: wait for it, or work in a second worktree",
    )


def check_settings(c: WorktreeCtx) -> Check:
    if not c.target.settings:
        return Check.passed("not a settings file")
    s = c.transcripts.session.get()
    if any(r.skill == "update-config" for ledger in s.everyone for r in ledger.of(SkillRan)):
        return Check.passed("update-config ran in this session")
    return Check.failed(
        f"{c.target.via} writes {c.target.path} without the update-config skill",
        "run the update-config skill, which validates settings.json, and make the change through it",
    )


def _text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


R1 = Requirement("G8.R1", "pgrep before writing into a delegated worktree", check_pgrep)
R2 = Requirement("G8.R2", "settings edits go through update-config", check_settings, advisory=True)


class WorktreeGate:
    name = "G8"
    event = Event.PRE_TOOL_USE

    def __init__(self, tools: FrozenSet[str], trigger_literals: Optional[Tuple[str, ...]]) -> None:
        self.tools = tools
        self.trigger_literals = trigger_literals

    def subjects(self, hook: HookCall) -> Tuple[Target, ...]:
        return find_targets(hook)

    def decide(self, subjects: Sequence[Target], transcripts: Transcripts, env: Env) -> Tuple[Decision, ...]:
        escapes = transcripts.escapes()
        return tuple(
            adjudicate(self.name, f"{t.via} on {t.path}", (R1, R2), WorktreeCtx(transcripts.hook, t, transcripts), escapes)
            for t in subjects
        )


BASH_LITERALS = (
    "git commit", "git reset", "git checkout", "git rebase", "git stash", "git clean", "git merge", "git push",
    "rm -r", "rm -f", "rm -rf", "rm -R", "rm --recursive", "rm --force", "settings",
    *(f"git -* {verb}" for verb in ("commit", "reset", "checkout", "rebase", "stash", "clean", "merge", "push")),
)
BASH_GATE = WorktreeGate(frozenset({"Bash"}), BASH_LITERALS)
FILE_GATE = WorktreeGate(FILE_TOOLS, None)

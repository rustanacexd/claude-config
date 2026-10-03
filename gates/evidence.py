from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, NamedTuple, FrozenSet, Iterable, Iterator, List, Optional, Sequence, Tuple, Type, TypeVar

from core import Unavailable
from github import Surface, parse_ts


@dataclass(frozen=True)
class Word:
    text: str
    dynamic: bool


@dataclass(frozen=True)
class Invocation:
    tool: str
    sub: Tuple[str, ...]
    words: Tuple[Word, ...]
    workdir: Optional[Path]
    pipes_into: Tuple[str, ...]

    def has(self, *flags: str) -> bool:
        return any(w.text in flags or any(w.text.startswith(f + "=") for f in flags if f.startswith("--")) for w in self.words)

    def value_of(self, *flags: str) -> Optional[Word]:
        for i, w in enumerate(self.words):
            if w.text in flags:
                return self.words[i + 1] if i + 1 < len(self.words) else None
            for f in flags:
                if f.startswith("--") and w.text.startswith(f + "="):
                    return Word(w.text[len(f) + 1 :], w.dynamic)
        return None

    def positional(self, value_flags: FrozenSet[str]) -> Tuple[Word, ...]:
        out: List[Word] = []
        words = iter(self.words)
        for w in words:
            if w.text == "--":
                out.extend(words)
                break
            if w.text.startswith("-") and len(w.text) > 1:
                if w.text in value_flags:
                    next(words, None)
                continue
            out.append(w)
        return tuple(out)


class _W:
    __slots__ = ("text", "dynamic", "subs", "heredoc")

    def __init__(self) -> None:
        self.text = ""
        self.dynamic = False
        self.subs: List[list] = []
        self.heredoc: Optional[str] = None


_OPS = ("&&", "||", ";;", "|&", "<<<", "<<-", "<<", "&>>", "&>", ">>", ">&", "<&", ">|", "<>", ";", "&", "|", "(", ")", "<", ">")
_REDIRS = frozenset({"<<<", "<<-", "<<", "&>>", "&>", ">>", ">&", "<&", ">|", "<>", "<", ">"})
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!-]")


class _Lexer:
    def __init__(self, s: str) -> None:
        self.s = s
        self.i = 0
        self.expect_tag: Optional[str] = None
        self.pending: List[Tuple[_W, bool]] = []

    def lex(self, closer: bool = False) -> list:
        s, toks, w, depth = self.s, [], None, 0

        def flush() -> None:
            nonlocal w
            if w is not None:
                if self.expect_tag:
                    self.pending.append((w, self.expect_tag == "<<-"))
                    self.expect_tag = None
                toks.append(w)
                w = None

        while self.i < len(s):
            c = s[self.i]
            if c == ")" and closer and depth == 0:
                flush()
                self.i += 1
                return toks
            if c in " \t":
                flush()
                self.i += 1
            elif c == "\n":
                flush()
                toks.append("\n")
                self.i += 1
                self._bodies()
            elif c == "#" and w is None:
                while self.i < len(s) and s[self.i] != "\n":
                    self.i += 1
            elif c == "\\":
                if s[self.i + 1 : self.i + 2] != "\n":
                    w = w or _W()
                    w.text += s[self.i + 1 : self.i + 2]
                self.i += 2
            elif c == "'":
                w = w or _W()
                j = s.find("'", self.i + 1)
                j = len(s) if j < 0 else j
                w.text += s[self.i + 1 : j]
                self.i = j + 1
            elif c == '"':
                w = w or _W()
                self._dquote(w)
            elif c == "`":
                w = w or _W()
                self._backtick(w)
            elif c == "$":
                w = w or _W()
                self._dollar(w)
            elif c in "<>" and s[self.i + 1 : self.i + 2] == "(":
                w = w or _W()
                start = self.i
                self.i += 2
                w.subs.append(self.lex(closer=True))
                w.dynamic = True
                w.text += s[start : self.i]
            else:
                op = next((o for o in _OPS if s.startswith(o, self.i)), None)
                if op is None:
                    w = w or _W()
                    w.dynamic = w.dynamic or c in "*?["
                    w.text += c
                    self.i += 1
                    continue
                if op in _REDIRS and w is not None and w.text.isdigit() and not w.subs:
                    w = None
                flush()
                if closer and op == "(":
                    depth += 1
                elif closer and op == ")":
                    depth -= 1
                toks.append(op)
                self.i += len(op)
                if op in ("<<", "<<-"):
                    self.expect_tag = op
        flush()
        return toks

    def _bodies(self) -> None:
        for word, strip_tabs in self.pending:
            body = []
            while self.i < len(self.s):
                end = self.s.find("\n", self.i)
                end = len(self.s) if end < 0 else end
                line = self.s[self.i : end]
                self.i = end + 1
                if (line.lstrip("\t") if strip_tabs else line) == word.text:
                    break
                body.append(line)
            word.heredoc = "\n".join(body)
        self.pending = []

    def _dquote(self, w: _W) -> None:
        s = self.s
        self.i += 1
        while self.i < len(s):
            c = s[self.i]
            if c == '"':
                self.i += 1
                return
            if c == "\\" and s[self.i + 1 : self.i + 2] in ('$', '`', '"', "\\", "\n"):
                w.text += s[self.i + 1] if s[self.i + 1] != "\n" else ""
                self.i += 2
            elif c == "$":
                self._dollar(w)
            elif c == "`":
                self._backtick(w)
            else:
                w.text += c
                self.i += 1

    def _backtick(self, w: _W) -> None:
        j = self.i + 1
        while j < len(self.s) and self.s[j] != "`":
            j += 2 if self.s[j] == "\\" else 1
        w.subs.append(_Lexer(self.s[self.i + 1 : j]).lex())
        w.dynamic = True
        w.text += self.s[self.i : j + 1]
        self.i = j + 1

    def _dollar(self, w: _W) -> None:
        s, start = self.s, self.i
        nxt = s[self.i + 1 : self.i + 2]
        if s.startswith("$((", self.i):
            depth, self.i = 2, self.i + 3
            while self.i < len(s) and depth:
                depth += {"(": 1, ")": -1}.get(s[self.i], 0)
                self.i += 1
        elif nxt == "(":
            self.i += 2
            w.subs.append(self.lex(closer=True))
        elif nxt == "{":
            j = s.find("}", self.i)
            self.i = len(s) if j < 0 else j + 1
        else:
            m = _NAME.match(s, self.i + 1)
            if not m:
                w.text += "$"
                self.i += 1
                return
            self.i = m.end()
        w.dynamic = True
        w.text += s[start : self.i]


_SEPARATORS = frozenset({";", "&&", "||", "&", "\n", "(", ")", ";;"})
_KEYWORDS = frozenset({"!", "{", "}", "do", "then", "else", "elif", "if", "while", "until", "fi", "done", "esac", "time"})
_HEADERS = frozenset({"for", "select", "case", "function"})
class Wrapper(NamedTuple):
    value_flags: FrozenSet[str]
    leading_args: int = 0


_WRAPPERS = {
    "env": Wrapper(frozenset({"-u", "-C", "-S"})),
    "command": Wrapper(frozenset()),
    "builtin": Wrapper(frozenset()),
    "exec": Wrapper(frozenset()),
    "nohup": Wrapper(frozenset()),
    "sudo": Wrapper(frozenset({"-u", "-g"})),
    "nice": Wrapper(frozenset({"-n"})),
    "xargs": Wrapper(frozenset({"-n", "-I", "-P", "-L", "-d", "-s", "-E"})),
    "timeout": Wrapper(frozenset({"-s", "-k", "--signal", "--kill-after"}), leading_args=1),
    "caffeinate": Wrapper(frozenset({"-t", "-w"})),
    "stdbuf": Wrapper(frozenset({"-i", "-o", "-e"})),
}
_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_SCRIPT_FLAG = re.compile(r"-[A-Za-z]*c[A-Za-z]*")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_GIT_VALUE_FLAGS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})


def _strip(argv: List[_W]) -> List[_W]:
    while argv:
        head = argv[0].text
        if _ASSIGNMENT.match(head) or head in _KEYWORDS:
            argv = argv[1:]
        elif head in _HEADERS:
            return []
        elif head in _WRAPPERS:
            wrapper, argv = _WRAPPERS[head], argv[1:]
            while argv and (argv[0].text.startswith("-") or (head == "env" and _ASSIGNMENT.match(argv[0].text))):
                argv = argv[2:] if argv[0].text in wrapper.value_flags else argv[1:]
            argv = argv[wrapper.leading_args :]
        else:
            return argv
    return argv


def _cd(workdir: Optional[Path], args: Sequence) -> Optional[Path]:
    if not args:
        return Path.home()
    target = args[0]
    if target.dynamic or target.text == "-":
        return None
    path = Path(os.path.expanduser(target.text))
    if path.is_absolute():
        return path
    return workdir / path if workdir is not None else None


def _split_sub(tool: str, words: List[Word], workdir: Optional[Path]) -> Tuple[Tuple[str, ...], Tuple[Word, ...], Optional[Path]]:
    if tool == "git":
        while words and words[0].text.startswith("-"):
            flag = words[0].text
            if flag in _GIT_VALUE_FLAGS and len(words) > 1:
                if flag == "-C":
                    workdir = _cd(workdir, [words[1]])
                words = words[2:]
            else:
                words = words[1:]
        return tuple(w.text for w in words[:1]), tuple(words[1:]), workdir
    if tool == "gh":
        n = 1 if words and words[0].text == "api" else 2
        sub: List[str] = []
        while words and len(sub) < n and not words[0].text.startswith("-"):
            sub.append(words[0].text)
            words = words[1:]
        return tuple(sub), tuple(words), workdir
    return (), tuple(words), workdir


def _build(toks: list, workdir: Optional[Path], out: List[Invocation]) -> Optional[Path]:
    pipelines: List[List[List]] = [[[]]]
    for t in toks:
        if t in ("|", "|&"):
            pipelines[-1].append([])
        elif isinstance(t, str) and t in _SEPARATORS:
            pipelines.append([[]])
        else:
            pipelines[-1][-1].append(t)

    for pipe in pipelines:
        segments = []
        for seg in pipe:
            argv: List[_W] = []
            heredocs: List[str] = []
            redirect = False
            for t in seg:
                if isinstance(t, str):
                    redirect = True
                    continue
                for sub in t.subs:
                    _build(sub, workdir, out)
                if redirect:
                    if t.heredoc is not None:
                        heredocs.append(t.heredoc)
                    redirect = False
                else:
                    argv.append(t)
            argv = _strip(argv)
            segments.append((argv, heredocs, os.path.basename(argv[0].text) if argv else ""))

        for k, (argv, heredocs, tool) in enumerate(segments):
            if not argv:
                continue
            if tool == "cd":
                workdir = _cd(workdir, argv[1:])
                continue
            if tool in _SHELLS:
                texts = [w.text for w in argv[1:]]
                flag = next((i for i, t in enumerate(texts[:-1]) if _SCRIPT_FLAG.fullmatch(t)), None)
                scripts = [texts[flag + 1]] if flag is not None else heredocs
                for script in scripts:
                    _build(_Lexer(script).lex(), workdir, out)
            if tool == "eval":
                _build(_Lexer(" ".join(w.text for w in argv[1:])).lex(), workdir, out)
            words = [Word(w.text, w.dynamic) for w in argv[1:]]
            sub, rest, wd = _split_sub(tool, words, workdir)
            out.append(Invocation(tool, sub, rest, wd, tuple(t for _, _, t in segments[k + 1 :] if t)))
    return workdir


def parse_shell(command: str, start_dir: Optional[Path]) -> Tuple[Invocation, ...]:
    out: List[Invocation] = []
    _build(_Lexer(command).lex(), start_dir, out)
    return tuple(out)


@dataclass(frozen=True, order=True)
class Stamp:
    line: int
    at: datetime


@dataclass(frozen=True)
class Human:
    stamp: Stamp
    text: str


@dataclass(frozen=True)
class Compacted:
    stamp: Stamp


@dataclass(frozen=True)
class Advised:
    stamp: Stamp


@dataclass(frozen=True)
class Read:
    stamp: Stamp
    path: str
    complete: bool


@dataclass(frozen=True)
class Fetched:
    stamp: Stamp
    surfaces: FrozenSet[Surface]
    pr: Optional[int]


@dataclass(frozen=True)
class Posted:
    stamp: Stamp
    ids: Optional[FrozenSet[str]]
    pr: Optional[int]
    done_at: datetime

    def window_contains(self, created_at: datetime) -> bool:
        return self.stamp.at - SELF_POST_SLACK <= created_at <= self.done_at + SELF_POST_SLACK


@dataclass(frozen=True)
class Pushed:
    stamp: Stamp


@dataclass(frozen=True)
class Committed:
    stamp: Stamp
    no_verify: bool


@dataclass(frozen=True)
class Declared:
    stamp: Stamp
    line: str


Event = object
E = TypeVar("E")


@dataclass(frozen=True)
class Result:
    text: str
    is_error: bool
    at: datetime


_PUSHES = frozenset({("git", ("push",)), ("gh", ("stack", "push")), ("gh", ("stack", "submit")), ("gh", ("stack", "sync"))})
_WRITE_METHODS = frozenset({"POST", "PATCH", "PUT"})
_FIELD_FLAGS = ("-f", "-F", "--field", "--raw-field")
_COMMENT_PATH = re.compile(r"(?:^|/)(issues|pulls)/(\d+)/(comments|reviews)\b")
_PATH_SURFACE = {("issues", "comments"): Surface.ISSUE, ("pulls", "reviews"): Surface.REVIEW, ("pulls", "comments"): Surface.INLINE}
_PARTIAL_READERS = frozenset({"head", "tail", "sed", "awk", "grep", "less", "more", "cut"})
_PR_VIEW_VALUE_FLAGS = frozenset({"--json", "-q", "--jq", "-t", "--template", "-R", "--repo"})
_POST_VALUE_FLAGS = frozenset({"-b", "--body", "-F", "--body-file", "-R", "--repo"})
_COMMENT_ID = re.compile(r"#(?:issuecomment-|pullrequestreview-|discussion_r)(\d+)|\"id\":\s*(\d+)")
_POST_PATH = re.compile(r"(?:^|/)(?:issues|pulls)/(\d+)/")
SELF_POST_SLACK = timedelta(seconds=5)


def _pr_number(text: str) -> Optional[int]:
    m = re.fullmatch(r"#?(\d+)", text) or re.search(r"/pull/(\d+)", text)
    return int(m.group(1)) if m else None


def is_post(inv: Invocation) -> bool:
    if inv.tool != "gh":
        return False
    if inv.sub in (("pr", "comment"), ("pr", "review"), ("issue", "comment")):
        return True
    if inv.sub == ("api",):
        if inv.words and inv.words[0].text == "graphql":
            return any("mutation" in w.text for w in inv.words)
        method = inv.value_of("-X", "--method")
        return method.text.upper() in _WRITE_METHODS if method else inv.has(*_FIELD_FLAGS)
    return False


def _push(inv: Invocation, stamp: Stamp, result: Optional[Result]) -> Iterable[Event]:
    if (inv.tool, inv.sub) in _PUSHES:
        yield Pushed(stamp)  # failed or not: `git push -q | tail -1` hides the exit code


def _commit(inv: Invocation, stamp: Stamp, result: Optional[Result]) -> Iterable[Event]:
    if inv.tool == "git" and inv.sub == ("commit",):
        yield Committed(stamp, inv.has("--no-verify", "-n"))


def _post(inv: Invocation, stamp: Stamp, result: Optional[Result]) -> Iterable[Event]:
    if not result or not is_post(inv):
        return
    if inv.sub == ("api",):
        paths = [m for w in inv.words for m in [_POST_PATH.search(w.text)] if m]
        pr = int(paths[0].group(1)) if paths else None
    else:
        selector = inv.positional(_POST_VALUE_FLAGS)
        pr = _pr_number(selector[0].text) if selector else None
    ids = frozenset(a or b for a, b in _COMMENT_ID.findall(result.text))
    yield Posted(stamp, ids or None, pr, result.at)


def _fetch(inv: Invocation, stamp: Stamp, result: Optional[Result]) -> Iterable[Event]:
    if not result or result.is_error or inv.tool != "gh" or is_post(inv):
        return
    surfaces = set()
    pr = None
    if inv.sub == ("pr", "view"):
        if inv.has("--comments"):
            surfaces |= {Surface.ISSUE, Surface.REVIEW}
        fields = inv.value_of("--json")
        names = set(fields.text.split(",")) if fields else set()
        surfaces |= {s for name, s in (("comments", Surface.ISSUE), ("reviews", Surface.REVIEW)) if name in names}
        selector = inv.positional(_PR_VIEW_VALUE_FLAGS)
        pr = _pr_number(selector[0].text) if selector else None
    elif inv.sub == ("api",):
        for w in inv.words:
            m = _COMMENT_PATH.search(w.text)
            if m:
                surfaces.add(_PATH_SURFACE[(m.group(1), m.group(3))])
                pr = int(m.group(2))
        if inv.words and inv.words[0].text == "graphql" and any("reviewThreads" in w.text for w in inv.words):
            surfaces.add(Surface.INLINE)
    if surfaces:
        yield Fetched(stamp, frozenset(surfaces), pr)


def _read(inv: Invocation, stamp: Stamp, result: Optional[Result]) -> Iterable[Event]:
    # is_error is the exit code of the whole chained command, so `cat f; ls missing` still showed f
    if not result or inv.tool not in _PARTIAL_READERS | {"cat"}:
        return
    complete = inv.tool == "cat" and not inv.pipes_into
    for w in inv.words:
        if not w.text.startswith("-"):
            yield Read(stamp, w.text, complete)


Classifier = Callable[[Invocation, Stamp, Optional[Result]], Iterable[Event]]
CLASSIFIERS: Tuple[Classifier, ...] = (_push, _commit, _post, _fetch, _read)


_TASK_TOOLS = frozenset({"TaskCreate", "TaskUpdate", "TodoWrite"})
_EDIT_TOOLS = {"Write": ("content",), "Edit": ("new_string",), "MultiEdit": ("edits",)}
_LOCAL_COMPACT = "<local-command-stdout>Compacted"


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _text(content: object) -> Optional[str]:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if any(isinstance(x, dict) and x.get("type") == "tool_result" for x in content):
            return None
        return " ".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text")
    return None


_WRAPPER_TAGS = (
    "system-reminder", "command-name", "command-message", "command-args", "local-command-stdout",
    "local-command-stderr", "local-command-caveat", "task-notification", "bash-input", "bash-stdout", "bash-stderr",
    "assistant_citations", "ci-monitor-event", "create-pr-command", "launch-selected-element", "pasted_content",
    "user-prompt-submit-hook",
)
_WRAPPER_BLOCK = re.compile(r"<(%s)\b[^>]*>.*?(?:</\1>|\Z)" % "|".join(_WRAPPER_TAGS), re.S)


def _human(rec: dict, text: str) -> Optional[str]:
    origin = rec.get("origin")
    kind = origin.get("kind", "human") if isinstance(origin, dict) else "human"
    if rec.get("isMeta") or rec.get("isCompactSummary") or kind != "human" or rec.get("turnOrigin") == "task_notification":
        return None
    m = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
    if m:
        return m.group(1).strip() or None
    return _WRAPPER_BLOCK.sub("", text).strip() or None


def _result_text(item: dict) -> str:
    content = item.get("content")
    return content if isinstance(content, str) else " ".join(_strings(content))


def _tool_events(item: dict, stamp: Stamp, cwd: Optional[Path], result: Optional[Result]) -> Iterator[Event]:
    name, inp = item.get("name"), item.get("input") or {}
    if name == "Bash":
        for inv in parse_shell(str(inp.get("command") or ""), cwd):
            for classify in CLASSIFIERS:
                yield from classify(inv, stamp, result)
    elif name == "Read" and result and not result.is_error:
        yield Read(stamp, str(inp.get("file_path", "")), inp.get("offset") is None and inp.get("limit") is None)
    elif name in _TASK_TOOLS:
        for s in _strings(inp):
            for line in s.splitlines():
                yield Declared(stamp, line)
    elif name in _EDIT_TOOLS:
        path = os.path.basename(str(inp.get("file_path", ""))).lower()
        if "todo" in path and path.endswith(".md"):
            for s in _strings([inp.get(k) for k in _EDIT_TOOLS[name]]):
                for line in s.splitlines():
                    yield Declared(stamp, line)


@dataclass(frozen=True)
class Ledger:
    source: str
    by_kind: Dict[type, Tuple[Event, ...]]

    def of(self, kind: Type[E]) -> Tuple[E, ...]:
        return self.by_kind.get(kind, ())

    def last(self, kind: Type[E]) -> Optional[E]:
        events = self.of(kind)
        return events[-1] if events else None

    def where(self, stamp: Stamp) -> str:
        return f"{self.source}:{stamp.line}"


def _records(path: Path) -> List[Tuple[int, dict]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise Unavailable(f"cannot read transcript {path}: {exc}", "this is a harness problem; tell the user") from exc
    out = []
    for n, line in enumerate(lines, 1):
        try:
            rec = json.loads(line)
        except ValueError:
            continue  # a torn last line while the harness is writing
        if isinstance(rec, dict):
            out.append((n, rec))
    if not out:
        raise Unavailable(f"transcript {path} has no readable records", "this is a harness problem; tell the user")
    return out


def _owns(rec: dict, tool_use_id: str) -> bool:
    content = (rec.get("message") or {}).get("content")
    return rec.get("type") == "assistant" and isinstance(content, list) and any(
        isinstance(c, dict) and c.get("type") == "tool_use" and c.get("id") == tool_use_id for c in content
    )


def load_ledger(path: Path, *, drop_sidechain: bool, cut_at_tool_use: Optional[str]) -> Ledger:
    """Cut strictly before the record carrying `cut_at_tool_use` when it is on disk, else keep the whole file.
    The harness writes the gated call's own record before PreToolUse only sometimes, and never its result."""
    records = _records(path)
    if cut_at_tool_use:
        cut = next((i for i, (_, rec) in enumerate(records) if _owns(rec, cut_at_tool_use)), None)
        if cut is not None:
            records = records[:cut]

    results: Dict[str, Result] = {}
    for _, rec in records:
        content = (rec.get("message") or {}).get("content")
        if rec.get("type") == "user" and isinstance(content, list) and rec.get("timestamp"):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    results[str(c.get("tool_use_id"))] = Result(_result_text(c), bool(c.get("is_error")), parse_ts(rec["timestamp"]))

    events: List[Event] = []
    for line, rec in records:
        if drop_sidechain and rec.get("isSidechain"):
            continue
        ts = rec.get("timestamp")
        if not ts:
            continue
        stamp = Stamp(line, parse_ts(ts))
        kind = rec.get("type")
        if kind == "system" and rec.get("subtype") == "compact_boundary":
            events.append(Compacted(stamp))
        elif kind == "user":
            text = _text((rec.get("message") or {}).get("content"))
            if text is None:
                continue
            if text.lstrip().startswith(_LOCAL_COMPACT):
                events.append(Compacted(stamp))
            human = _human(rec, text)
            if human:
                events.append(Human(stamp, human))
        elif kind == "assistant":
            cwd = Path(rec["cwd"]) if rec.get("cwd") else None
            for item in (rec.get("message") or {}).get("content") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "server_tool_use" and item.get("name") == "advisor":
                    events.append(Advised(stamp))
                elif item.get("type") == "tool_use":
                    events.extend(_tool_events(item, stamp, cwd, results.get(str(item.get("id")))))

    by_kind: Dict[type, List[Event]] = {}
    for e in events:
        by_kind.setdefault(type(e), []).append(e)
    return Ledger(path.name, {k: tuple(v) for k, v in by_kind.items()})


@dataclass(frozen=True)
class Session:
    root: Ledger
    actor: Ledger

    @property
    def ledgers(self) -> Tuple[Ledger, ...]:
        return (self.root,) if self.actor is self.root else (self.root, self.actor)

    def own_comment_ids(self) -> FrozenSet[str]:
        return frozenset(i for ledger in self.ledgers for p in ledger.of(Posted) for i in p.ids or ())

    def may_have_posted(self, comment_id: str, pr: int, created_at: datetime) -> bool:
        return any(
            comment_id in p.ids if p.ids is not None else p.pr in (None, pr) and p.window_contains(created_at)
            for ledger in self.ledgers
            for p in ledger.of(Posted)
        )

    def declared(self) -> Sequence[Tuple[Declared, Ledger]]:
        return [(d, ledger) for ledger in self.ledgers for d in ledger.of(Declared)]


def subagent_path(transcript_path: Path, agent_id: str) -> Path:
    return transcript_path.with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"


def load_session(transcript_path: Path, agent_id: Optional[str], tool_use_id: Optional[str]) -> Session:
    """`transcript_path` is the main session file even inside a subagent; `agent_id` names the acting one."""
    if not agent_id:
        root = load_ledger(transcript_path, drop_sidechain=True, cut_at_tool_use=tool_use_id)
        return Session(root, root)
    root = load_ledger(transcript_path, drop_sidechain=True, cut_at_tool_use=None)
    actor = load_ledger(subagent_path(transcript_path, agent_id), drop_sidechain=False, cut_at_tool_use=tool_use_id)
    return Session(root, actor)

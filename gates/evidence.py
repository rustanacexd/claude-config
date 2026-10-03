from __future__ import annotations

import functools
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, NamedTuple, FrozenSet, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple, Type, TypeVar

from core import Escape, HookCall, Loaded, Unavailable, collect_escapes
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
    global_opts: Tuple[Word, ...] = ()
    redirects_to: Tuple[Word, ...] = ()

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
    __slots__ = ("text", "dynamic", "subs", "heredoc", "refs")

    def __init__(self) -> None:
        self.text = ""
        self.dynamic = False
        self.subs: List[list] = []
        self.heredoc: Optional[str] = None
        self.refs: List[str] = []

    def word(self) -> "Word":
        return Word(self.text, self.dynamic or bool(self.refs))


_OPS = ("&&", "||", ";;", "|&", "<<<", "<<-", "<<", "&>>", "&>", ">>", ">&", "<&", ">|", "<>", ";", "&", "|", "(", ")", "<", ">")
_REDIRS = frozenset({"<<<", "<<-", "<<", "&>>", "&>", ">>", ">&", "<&", ">|", "<>", "<", ">"})
_OUTPUT_REDIRS = frozenset({">", ">>", ">|", "&>", "&>>"})
_VAR = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
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
            name = s[start + 2 : j]
            if _VAR.fullmatch(name):
                w.refs.append(name)
                w.text += s[start : self.i]
                return
        else:
            m = _NAME.match(s, self.i + 1)
            if not m:
                w.text += "$"
                self.i += 1
                return
            self.i = m.end()
            if _VAR.fullmatch(m.group()):
                w.refs.append(m.group())
                w.text += s[start : self.i]
                return
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
_GIT_VALUE_FLAGS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--attr-source"})


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


def _split_sub(tool: str, words: List[Word], workdir: Optional[Path]) -> Tuple[Tuple[str, ...], Tuple[Word, ...], Optional[Path], Tuple[Word, ...]]:
    if tool == "git":
        global_opts: List[Word] = []
        while words and words[0].text.startswith("-"):
            flag = words[0].text
            n = 2 if flag in _GIT_VALUE_FLAGS and len(words) > 1 else 1
            if n == 2 and flag == "-C":
                workdir = _cd(workdir, [words[1]])
            global_opts += words[:n]
            words = words[n:]
        return tuple(w.text for w in words[:1]), tuple(words[1:]), workdir, tuple(global_opts)
    if tool == "gh":
        n = 1 if words and words[0].text == "api" else 2
        sub: List[str] = []
        while words and len(sub) < n and not words[0].text.startswith("-"):
            sub.append(words[0].text)
            words = words[1:]
        return tuple(sub), tuple(words), workdir, ()
    return (), tuple(words), workdir, ()


def _resolve(w: _W, env: Dict[str, str]) -> None:
    for name in set(w.refs) & env.keys():
        w.text = re.sub(r"\$\{" + name + r"\}|\$" + name + r"(?![A-Za-z0-9_])", lambda _: env[name], w.text)
    w.refs = [n for n in w.refs if n not in env]


def _build(toks: list, workdir: Optional[Path], out: List[Invocation], env: Optional[Dict[str, str]] = None) -> Optional[Path]:
    env = {} if env is None else env
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
            outputs: List[Word] = []
            redirect: Optional[str] = None
            for t in seg:
                if isinstance(t, str):
                    redirect = t
                    continue
                _resolve(t, env)
                for sub in t.subs:
                    _build(sub, workdir, out, env)
                if redirect is None:
                    argv.append(t)
                elif t.heredoc is not None:
                    heredocs.append(t.heredoc)
                elif redirect in _OUTPUT_REDIRS:
                    outputs.append(t.word())
                redirect = None
            assigned = [w for w in argv if _ASSIGNMENT.match(w.text)]
            argv = _strip(argv)
            if assigned and not argv:
                for w in assigned:
                    if not w.word().dynamic:
                        name, value = w.text.split("=", 1)
                        env[name] = os.path.expanduser(value)
            segments.append((argv, heredocs, os.path.basename(argv[0].text) if argv else "", tuple(outputs)))

        for k, (argv, heredocs, tool, targets) in enumerate(segments):
            if not argv:
                continue
            if tool == "cd":
                workdir = _cd(workdir, [w.word() for w in argv[1:]])
                continue
            if tool in _SHELLS:
                texts = [w.text for w in argv[1:]]
                flag = next((i for i, t in enumerate(texts[:-1]) if _SCRIPT_FLAG.fullmatch(t)), None)
                scripts = [texts[flag + 1]] if flag is not None else heredocs
                for script in scripts:
                    _build(_Lexer(script).lex(), workdir, out)
            if tool == "eval":
                _build(_Lexer(" ".join(w.text for w in argv[1:])).lex(), workdir, out)
            words = [w.word() for w in argv[1:]]
            sub, rest, wd, global_opts = _split_sub(tool, words, workdir)
            out.append(Invocation(tool, sub, rest, wd, tuple(t for _, _, t, _ in segments[k + 1 :] if t), global_opts, targets))
    return workdir


def parse_shell(command: str, start_dir: Optional[Path]) -> Tuple[Invocation, ...]:
    out: List[Invocation] = []
    _build(_Lexer(command).lex(), start_dir, out)
    return tuple(out)


@dataclass(frozen=True, order=True)
class Stamp:
    line: int
    at: datetime
    msg_id: Optional[str] = field(default=None, compare=False)


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
    shown: str = field(default="", compare=False, repr=False)

    def covers_file(self) -> bool:
        try:
            lines = Path(os.path.expanduser(self.path)).read_text(errors="replace").splitlines()
        except OSError:
            return False
        wanted = [line.strip() for line in lines if line.strip()]
        return bool(wanted) and all(line in self.shown for line in wanted)


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
class SkillRan:
    stamp: Stamp
    skill: str
    args: str


@dataclass(frozen=True)
class Spawned:
    stamp: Stamp
    subagent_type: str
    model: Optional[str]
    description: str
    prompt: str
    isolation: Optional[str]
    agent_id: Optional[str] = None


@dataclass(frozen=True)
class Messaged:
    stamp: Stamp
    to: str
    resumed: Optional[str]


@dataclass(frozen=True)
class Pgrep:
    stamp: Stamp
    args: Tuple[str, ...]


@dataclass(frozen=True)
class Edited:
    stamp: Stamp
    path: str


@dataclass(frozen=True)
class TaskOp:
    stamp: Stamp
    tool: str
    task_id: Optional[str]
    subject: str
    description: str
    status: Optional[str]
    todo_file: Optional[str] = None

    @property
    def lines(self) -> Sequence[str]:
        text = [self.subject, self.description]
        if self.todo_file:
            try:
                text.append(Path(self.todo_file).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
        return [line for t in text for line in t.splitlines()]


@dataclass(frozen=True)
class Tested:
    stamp: Stamp
    command: str


@dataclass(frozen=True)
class DetachedAppScript:
    tool: str
    script: str
    up: str
    down: str


@dataclass(frozen=True)
class AppControl:
    stamp: Stamp
    app: DetachedAppScript
    up: bool


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


_COMMIT_VALUE_FLAGS = frozenset({"-m", "-F", "-c", "-C", "-t", "--message", "--file", "--template", "--reuse-message",
                                  "--reedit-message", "--author", "--date", "--cleanup", "--fixup", "--squash", "--trailer"})


SHORTEST_NO_VERIFY_EVEN_IF_GIT_CALLS_IT_AMBIGUOUS = "--no-v"


def _is_no_verify(flag: str) -> bool:
    """git takes any unambiguous prefix of a long option."""
    return flag.startswith(SHORTEST_NO_VERIFY_EVEN_IF_GIT_CALLS_IT_AMBIGUOUS) and "--no-verify".startswith(flag)


def _overrides_hooks_path(global_opts: Sequence[Word]) -> bool:
    words = iter(global_opts)
    for w in words:
        if w.text in ("-c", "--config-env"):
            setting = next(words, Word("", False)).text
        elif w.text.startswith("--config-env="):
            setting = w.text[len("--config-env=") :]
        else:
            continue
        if setting.split("=", 1)[0].lower() == "core.hookspath":
            return True
    return False


def skips_hooks(inv: Invocation) -> bool:
    if inv.tool != "git" or inv.sub not in (("commit",), ("push",)):
        return False
    if _overrides_hooks_path(inv.global_opts):
        return True
    words = iter(inv.words)
    for w in words:
        if w.text == "--":
            return False
        if _is_no_verify(w.text):
            return True
        if w.text in _COMMIT_VALUE_FLAGS:
            next(words, None)
        elif inv.sub == ("commit",) and w.text.startswith("-") and not w.text.startswith("--"):
            for c in w.text[1:]:
                if c == "n":
                    return True
                if "-" + c in _COMMIT_VALUE_FLAGS:
                    break
    return False


def _commit(inv: Invocation, stamp: Stamp, result: Optional[Result]) -> Iterable[Event]:
    if inv.tool == "git" and inv.sub == ("commit",):
        yield Committed(stamp, skips_hooks(inv))


_TEST_RUNNERS = (
    ("npm", ("test",)), ("npm", ("t",)), ("npm", ("run", "test")), ("npm", ("run", "preflight")), ("npm", ("run", "typecheck")),
    ("npm", ("run", "check:")), ("pytest", ()), ("jest", ()), ("npx", ("jest",)), ("python", ("-m", "unittest")),
    ("python", ("-m", "pytest")), ("go", ("test",)), ("cargo", ("test",)), ("make", ("test",)),
)


def _tested(inv: Invocation, stamp: Stamp, result: Optional[Result]) -> Iterable[Event]:
    tool = re.sub(r"^python3(\.\d+)?$", "python", inv.tool)
    words = [w.text for w in inv.words]
    hit = tool.startswith("verify") or any(
        tool == t and len(words) >= len(prefix) and all(w == p or (p.endswith(":") and w.startswith(p)) for w, p in zip(words, prefix))
        for t, prefix in _TEST_RUNNERS
    )
    if hit:
        yield Tested(stamp, " ".join([inv.tool, *words]))


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
            yield Read(stamp, w.text, complete, result.text)


_IN_PLACE_SCRIPT_FLAGS = {"sed": frozenset({"-e", "--expression", "-f", "--file"}), "perl": frozenset({"-e", "-E"})}
_TAKES_VALUE = {"sed": "efl", "perl": "eEIMmxCdD"}
_PERL_DIGIT_SWITCHES = re.compile(r"[0l]\d*")


def _in_place(tool: str, flag: str) -> bool:
    if flag.startswith("--in-place"):
        return True
    if not flag.startswith("-") or flag.startswith("--"):
        return False
    for c in _PERL_DIGIT_SWITCHES.sub("", flag[1:]) if tool == "perl" else flag[1:]:
        if c == "i":
            return True
        if c in _TAKES_VALUE[tool]:
            return False
    return False


def _written(inv: Invocation) -> Iterator[Word]:
    yield from inv.redirects_to
    if inv.tool == "tee":
        yield from inv.positional(frozenset())
    elif inv.tool in _IN_PLACE_SCRIPT_FLAGS and any(_in_place(inv.tool, w.text) for w in inv.words):
        script_flags = _IN_PLACE_SCRIPT_FLAGS[inv.tool]
        files = [w for w in inv.positional(script_flags) if w.text]
        yield from files if inv.has(*script_flags) else files[1:]


def _wrote(inv: Invocation, stamp: Stamp, result: Optional[Result]) -> Iterable[Event]:
    if result is not None and result.is_error:
        return
    for w in _written(inv):
        if w.dynamic or w.text in ("", "-") or w.text.startswith("/dev/"):
            continue
        path = Path(os.path.expanduser(w.text))
        if not path.is_absolute() and inv.workdir is not None:
            path = inv.workdir / path
        yield Edited(stamp, str(path))
        if is_todo(str(path)):
            yield TaskOp(stamp, "Bash", None, "", "", None, todo_file=str(path))


APP_SCRIPTS = (DetachedAppScript("npm", "e2e:control", "up", "down"),)


def _app_control(inv: Invocation, stamp: Stamp, result: Optional[Result]) -> Iterable[Event]:
    words = [w.text for w in inv.words]
    for app in APP_SCRIPTS:
        if inv.tool == app.tool and app.script in words:
            verb = next((w for w in words[words.index(app.script) + 1 :] if not w.startswith("-")), None)
            if verb in (app.up, app.down):
                yield AppControl(stamp, app, verb == app.up)


def _pgrep(inv: Invocation, stamp: Stamp, result: Optional[Result]) -> Iterable[Event]:
    if inv.tool == "pgrep":
        yield Pgrep(stamp, tuple(w.text for w in inv.words))


Classifier = Callable[[Invocation, Stamp, Optional[Result]], Iterable[Event]]
CLASSIFIERS: Tuple[Classifier, ...] = (_push, _commit, _post, _fetch, _read, _tested, _wrote, _app_control, _pgrep)


_EDIT_TOOLS = {"Write": ("content",), "Edit": ("new_string",), "MultiEdit": ("edits",), "NotebookEdit": ("new_source",)}
_TASK_CREATED = re.compile(r"Task #(\S+) created")
_COMMAND_NAME = re.compile(r"<command-name>/?([^<\s]+)</command-name>")
_COMMAND_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)
_AGENT_ID = re.compile(r"agentId: (\w+)")


def is_todo(path: str) -> bool:
    base = os.path.basename(path).lower()
    return "todo" in base and base.endswith(".md")


def skill_name(raw: str) -> str:
    return raw.strip().lstrip("/").rsplit(":", 1)[-1]
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


def _str(value: object) -> str:
    return "" if value is None else str(value)


def _opt_str(value: object) -> Optional[str]:
    return None if value is None else str(value)


def _resumed(result: Optional[Result]) -> Optional[str]:
    try:
        reply = json.loads(result.text) if result else None
    except ValueError:
        return None
    if not isinstance(reply, dict):
        return None
    pin = reply.get("pin")
    return _opt_str(reply.get("resumedAgentId") or (pin.get("id") if isinstance(pin, dict) else None))


def _tool_events(item: dict, stamp: Stamp, cwd: Optional[Path], result: Optional[Result]) -> Iterator[Event]:
    name, inp = item.get("name"), item.get("input") or {}
    if name == "Bash":
        for inv in parse_shell(_str(inp.get("command")), cwd):
            for classify in CLASSIFIERS:
                yield from classify(inv, stamp, result)
    elif name == "Read" and result and not result.is_error:
        yield Read(stamp, _str(inp.get("file_path")), inp.get("offset") is None and inp.get("limit") is None, result.text)
    elif name == "Skill":
        yield SkillRan(stamp, skill_name(_str(inp.get("skill"))), _str(inp.get("args")))
    elif name == "Agent":
        m = _AGENT_ID.search(result.text) if result else None
        yield Spawned(stamp, _str(inp.get("subagent_type")) or "general-purpose", inp.get("model"), _str(inp.get("description")),
                      _str(inp.get("prompt")), inp.get("isolation"), m.group(1) if m else None)
    elif name == "SendMessage":
        yield Messaged(stamp, _str(inp.get("to") or inp.get("recipient")), _resumed(result))
    elif name == "TaskCreate":
        m = _TASK_CREATED.search(result.text) if result else None
        yield TaskOp(stamp, name, m.group(1) if m else None, _str(inp.get("subject")), _str(inp.get("description")), "pending")
    elif name == "TaskUpdate":
        yield TaskOp(stamp, name, _opt_str(inp.get("taskId")), _str(inp.get("subject")), _str(inp.get("description")), inp.get("status"))
    elif name == "TodoWrite":
        for todo in inp.get("todos") or []:
            if isinstance(todo, dict):
                yield TaskOp(stamp, name, _opt_str(todo.get("id")), _str(todo.get("content")), "", todo.get("status"))
    elif name in _EDIT_TOOLS:
        if result is not None and result.is_error:
            return
        path = _str(inp.get("file_path") or inp.get("notebook_path"))
        yield Edited(stamp, path)
        if is_todo(path):
            yield TaskOp(stamp, name, None, "", "\n".join(_strings([inp.get(k) for k in _EDIT_TOOLS[name]])), None)


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
        stamp = Stamp(line, parse_ts(ts), (rec.get("message") or {}).get("id"))
        kind = rec.get("type")
        if kind == "system" and rec.get("subtype") == "compact_boundary":
            events.append(Compacted(stamp))
        elif kind == "user":
            text = _text((rec.get("message") or {}).get("content"))
            if text is None:
                continue
            if text.lstrip().startswith(_LOCAL_COMPACT):
                events.append(Compacted(stamp))
            command = _COMMAND_NAME.search(text) if not (rec.get("isMeta") or rec.get("isCompactSummary")) else None
            if command:
                args = _COMMAND_ARGS.search(text)
                events.append(SkillRan(stamp, skill_name(command.group(1)), args.group(1).strip() if args else ""))
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
    agents: Tuple[Ledger, ...] = ()

    @property
    def ledgers(self) -> Tuple[Ledger, ...]:
        return (self.root,) if self.actor is self.root else (self.root, self.actor)

    @property
    def everyone(self) -> Tuple[Ledger, ...]:
        return (self.root, *self.agents)

    def own_comment_ids(self) -> FrozenSet[str]:
        return frozenset(i for ledger in self.ledgers for p in ledger.of(Posted) for i in p.ids or ())

    def may_have_posted(self, comment_id: str, pr: int, created_at: datetime) -> bool:
        return any(
            comment_id in p.ids if p.ids is not None else p.pr in (None, pr) and p.window_contains(created_at)
            for ledger in self.ledgers
            for p in ledger.of(Posted)
        )

    def declared(self) -> Sequence[Tuple[str, str]]:
        return [(line, ledger.where(t.stamp)) for ledger in self.ledgers for t in ledger.of(TaskOp) for line in t.lines]

    def latest(self, kind: Type[E], where: Callable[[E], bool] = lambda e: True) -> Optional["Placed"]:
        per_file = [
            Placed(events[-1], ledger)
            for ledger in self.everyone
            for events in [[e for e in ledger.of(kind) if where(e)]]
            if events
        ]
        return max(per_file, key=lambda p: p.event.stamp.at, default=None)


@dataclass(frozen=True)
class Placed:
    event: Event
    ledger: Ledger

    def precedes(self, event: Event, ledger: Ledger) -> bool:
        if ledger is self.ledger:
            return self.event.stamp.line < event.stamp.line
        return self.event.stamp.at < event.stamp.at

    @property
    def where(self) -> str:
        return self.ledger.where(self.event.stamp)


TEMP_DIRS = ("/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/")


@functools.lru_cache(maxsize=256)
def git_root(path: str) -> Optional[Path]:
    """The work tree holding `path`: the nearest directory with a `.git` directory or file (a linked worktree)."""
    p = Path(os.path.realpath(path))
    for d in (p, *p.parents):
        if (d / ".git").exists():
            return d
    return None


def is_scratch(path: str) -> bool:
    return path.startswith(TEMP_DIRS) and git_root(path) is None


def subagent_path(transcript_path: Path, agent_id: str) -> Path:
    return transcript_path.with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"


def load_session(transcript_path: Path, agent_id: Optional[str], tool_use_id: Optional[str]) -> Session:
    """`transcript_path` is the main session file even inside a subagent; `agent_id` names the acting one."""
    actor_path = subagent_path(transcript_path, agent_id) if agent_id else None
    root = load_ledger(transcript_path, drop_sidechain=True, cut_at_tool_use=None if agent_id else tool_use_id)
    actor = load_ledger(actor_path, drop_sidechain=False, cut_at_tool_use=tool_use_id) if actor_path else root
    agents = []
    for path in sorted(transcript_path.with_suffix("").glob("subagents/agent-*.jsonl")):
        ledger = actor if path == actor_path else _other_agent(path)
        if ledger is not None:
            agents.append(ledger)
    return Session(root, actor, tuple(agents))


def _other_agent(path: Path) -> Optional[Ledger]:
    """Another agent's file may be empty or half-written because it just started; it then holds no evidence."""
    try:
        return load_ledger(path, drop_sidechain=False, cut_at_tool_use=None)
    except Unavailable:
        return None


POTETO_MARKERS = (b"poteto-mode", b"poteto-agent", b"pstack:poteto")
POTETO_AGENT = "pstack:poteto-agent"


class Transcripts:
    def __init__(self, hook: HookCall) -> None:
        self.hook = hook
        self._session: Optional[Loaded] = None

    @property
    def session(self) -> "Loaded[Session]":
        if self._session is None:
            self._session = Loaded.of(self._load)
        return self._session

    def _load(self) -> Session:
        try:
            return load_session(self.hook.transcript_path, self.hook.agent_id, self.hook.tool_use_id)
        except Unavailable:
            raise
        except Exception as exc:
            raise Unavailable(f"could not parse the transcript: {exc!r}", "report this gate bug to the user") from exc

    def escapes(self) -> "Escapes":
        return Escapes(self)

    def poteto_active(self) -> bool:
        if (self.hook.agent_type or "").startswith(POTETO_AGENT):
            return True
        if not self._may_mention_poteto():
            return False
        return any(r.skill == "poteto-mode" for ledger in self.session.get().ledgers for r in ledger.of(SkillRan))

    def _may_mention_poteto(self) -> bool:
        """A substring test on the raw files, so a session that never names poteto-mode is never parsed. An
        unreadable file answers yes, and the parse then reports why it cannot read it."""
        files = [self.hook.transcript_path]
        if self.hook.agent_id:
            files.append(subagent_path(self.hook.transcript_path, self.hook.agent_id))
        texts = [_bytes(f) for f in files]
        return None in texts or any(marker in t for t in texts for marker in POTETO_MARKERS)


class Escapes:
    """Declared skips, read only when a requirement fails, so a passing gate never parses the transcript."""

    def __init__(self, transcripts: Transcripts) -> None:
        self._transcripts = transcripts
        self._found: Optional[Mapping[str, Escape]] = None

    def get(self, rid: str) -> Optional[Escape]:
        if self._found is None:
            session = self._transcripts.session
            self._found = collect_escapes(session.value.declared()) if session.value else {}
        return self._found.get(rid)


def _bytes(path: Path) -> Optional[bytes]:
    try:
        return path.read_bytes()
    except OSError:
        return None

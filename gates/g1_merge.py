from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple

from core import Check, Decision, Env, HookCall, Loaded, Requirement, adjudicate, collect_escapes
from evidence import Advised, Compacted, Fetched, Human, Invocation, Pushed, Read, Session, Word, parse_shell
from github import GhCli, PrFacts, Surface

TRIGGER = "gh pr merge"
SHIPPING_PLAYBOOK = "playbooks/shipping.md"
TS_FLOOR = timedelta(seconds=1)  # GitHub floors timestamps to the second
RETRY_HINT = "If you just did this, run the merge again as its own command."
MERGE_VALUE_FLAGS = frozenset(
    {"--match-head-commit", "--repo", "-R", "--body", "-b", "--body-file", "-F", "--subject", "-t", "--author-email", "-A"}
)


@dataclass(frozen=True)
class MergeCall:
    inv: Invocation
    selector: Optional[Word]
    repo: Optional[Word]
    match_head: Optional[Word]
    workdir: Path

    @property
    def text(self) -> str:
        return " ".join(["gh pr merge", *(w.text for w in self.inv.words)])


def find_merges(hook: HookCall) -> Tuple[MergeCall, ...]:
    if hook.tool_name != "Bash":
        return ()
    return tuple(
        MergeCall(
            inv,
            next(iter(inv.positional(MERGE_VALUE_FLAGS)), None),
            inv.value_of("--repo", "-R"),
            inv.value_of("--match-head-commit"),
            inv.workdir or hook.cwd,
        )
        for inv in parse_shell(hook.command, hook.cwd)
        if inv.tool == "gh" and inv.sub == ("pr", "merge") and not inv.has("--disable-auto", "--help", "-h")
    )


@dataclass(frozen=True)
class MergeCtx:
    merge: MergeCall
    pr: Loaded[PrFacts]
    session: Loaded[Session]


def gather_pr(merge: MergeCall, env: Env) -> Loaded[PrFacts]:
    for w in (merge.selector, merge.repo):
        if w is not None and w.dynamic:
            return Loaded(
                None,
                f"the PR is named by a shell expression ({w.text})",
                "run one `gh pr merge <number> --repo <owner/name> --match-head-commit <sha>` per PR, with literal values",
            )
    return Loaded.of(
        lambda: GhCli(env.run, env.deadline).fetch(
            merge.selector.text if merge.selector else None, merge.repo.text if merge.repo else None, merge.workdir
        )
    )


def _merge_example(c: MergeCtx) -> str:
    pr = c.pr.value
    if pr is None:
        return "gh pr merge <number> --repo <owner/name> --squash --match-head-commit <the 40-character head SHA>"
    return f"gh pr merge {pr.number} --repo {pr.repo} --squash --match-head-commit {pr.head_sha}"


VERDICT = re.compile(r"\bPASS\+NOTES\b|\bPASS\b|\bFAIL\b")
SHA_TOKEN = re.compile(r"\b[0-9a-f]{8,40}\b", re.I)


def check_verdict(c: MergeCtx) -> Check:
    pr = c.pr.get()
    session = c.session.get()
    own = {cm.id for cm in pr.comments if session.may_have_posted(cm.id, pr.number, cm.created_at)}
    verdicts = [
        (cm, m.group(0), {s.lower() for s in SHA_TOKEN.findall(cm.body)})
        for cm in pr.comments
        if cm.surface is not Surface.INLINE
        for m in [VERDICT.search(cm.body)]
        if m
    ]
    on_head = [v for v in verdicts if any(pr.head_sha.startswith(s) for s in v[2])]
    independent = [v for v in on_head if v[0].id not in own]
    if independent and independent[-1][1] in ("PASS", "PASS+NOTES"):
        return Check.passed(f"{independent[-1][1]} on {pr.head_sha[:12]} at {independent[-1][0].url}")
    reasons = []
    if independent:
        reasons.append(f"the latest verdict on {pr.head_sha[:12]} is {independent[-1][1]} ({independent[-1][0].url})")
    else:
        reasons.append(f"no independent PASS or PASS+NOTES comment names the head {pr.head_sha[:12]}")
    self_posted = [v[0].url for v in on_head if v[0].id in own]
    if self_posted:
        reasons.append(f"this session posted {', '.join(self_posted)} itself, so it does not count")
    stale = sorted({s[:12] for v in verdicts if v not in on_head for s in v[2]})
    if stale:
        reasons.append(f"verdicts name other commits: {', '.join(stale)}")
    return Check.failed(
        "; ".join(reasons),
        f"have a verifier subagent that did not write the code post PASS or PASS+NOTES naming {pr.head_sha} "
        "on the PR (playbooks/shipping.md). Do not post it yourself.",
    )


def check_head_pin(c: MergeCtx) -> Check:
    w = c.merge.match_head
    if w is None:
        return Check.failed("the command has no --match-head-commit", _merge_example(c))
    if w.dynamic:
        return Check.failed(f"--match-head-commit {w.text} is a shell expression, not the SHA you verified", _merge_example(c))
    if not re.fullmatch(r"[0-9a-fA-F]{40}", w.text):
        return Check.failed(f"--match-head-commit {w.text} is not a full 40-character SHA", _merge_example(c))
    pr = c.pr.get()
    if w.text.lower() != pr.head_sha:
        return Check.failed(f"the pin is {w.text[:12]}, but the PR head is {pr.head_sha[:12]}", _merge_example(c))
    return Check.passed(f"pins the head {pr.head_sha[:12]}")


_READ_COMMAND = {
    Surface.ISSUE: "gh api repos/{repo}/issues/{n}/comments --paginate",
    Surface.REVIEW: "gh api repos/{repo}/pulls/{n}/reviews --paginate",
    Surface.INLINE: "gh api repos/{repo}/pulls/{n}/comments --paginate",
}


def check_comments_read(c: MergeCtx) -> Check:
    pr = c.pr.get()
    session = c.session.get()
    own = session.own_comment_ids()
    fetches = session.actor.of(Fetched)
    unread = []
    for surface in Surface:
        theirs = [cm for cm in pr.comments if cm.surface is surface and cm.body.strip() and cm.id not in own]
        if not theirs:
            continue
        newest = max(theirs, key=lambda cm: cm.changed_at)
        if not any(
            surface in f.surfaces and f.pr in (None, pr.number) and f.stamp.at >= newest.changed_at + TS_FLOOR
            for f in fetches
        ):
            unread.append((surface, newest))
    if not unread:
        return Check.passed("comments read after the newest change")
    detail = "; ".join(
        f"{s.value} comments: the newest is by {cm.author} at {cm.changed_at:%Y-%m-%dT%H:%M:%SZ} ({cm.url}), "
        f"and no {s.value} read started after it"
        for s, cm in unread
    )
    commands = " ; ".join(_READ_COMMAND[s].format(repo=pr.repo, n=pr.number) for s, _ in unread)
    return Check.failed(
        detail,
        f"in a call separate from the merge, run: {commands}. A bot review newer than your last push may still "
        f"be in progress: wait for it, then read again. {RETRY_HINT}",
    )


def check_advisor(c: MergeCtx) -> Check:
    session = c.session.get()
    pushes = [(p, ledger) for ledger in session.ledgers for p in ledger.of(Pushed)]
    last = max(pushes, key=lambda pl: pl[0].stamp.at, default=None)
    calls = [a for a in session.actor.of(Advised) if last is None or a.stamp.at > last[0].stamp.at]
    if calls:
        return Check.passed(f"advisor at {session.actor.where(calls[-1].stamp)}")
    since = f" after the last push ({last[1].where(last[0].stamp)} at {last[0].stamp.at:%H:%M:%S})" if last else ""
    return Check.failed(f"no advisor call{since}", f"call the advisor tool now. {RETRY_HINT}")


def check_playbook_read(c: MergeCtx) -> Check:
    actor = c.session.get().actor
    boundary = actor.last(Compacted)
    after = boundary.stamp.line if boundary else 0
    reads = [r for r in actor.of(Read) if r.path.endswith(SHIPPING_PLAYBOOK) and r.stamp.line > after]
    full = [r for r in reads if r.complete]
    if full:
        return Check.passed(f"read in full at {actor.where(full[-1].stamp)}")
    detail = f"no full read of {SHIPPING_PLAYBOOK}"
    if boundary:
        detail += f" since the compaction at {actor.where(boundary.stamp)}"
    if reads:
        detail += f"; partial reads at {', '.join(actor.where(r.stamp) for r in reads)} do not count"
    return Check.failed(detail, f"read {SHIPPING_PLAYBOOK} in full with the Read tool, or with `cat` and no pipe")


AUTH_VERB = re.compile(r"\b(merge|land|ship)\b", re.I)
NEGATION = re.compile(r"\b(don'?t|do not|never|not yet|hold off)\b[^.!?\n]{0,30}$", re.I)


def check_authority(c: MergeCtx) -> Check:
    session = c.session.get()
    for h in session.root.of(Human):
        for m in AUTH_VERB.finditer(h.text):
            if not NEGATION.search(h.text[: m.start()]):
                return Check.passed(f"user message at {session.root.where(h.stamp)} says {m.group(0)!r}")
    return Check.failed(
        "no user message asks to merge, land or ship without a negation before the verb",
        "ask the user to authorize landing this PR, then run the merge again",
    )


R1 = Requirement("G1.R1", "independent PASS on the exact head", check_verdict)
R2 = Requirement("G1.R2", "--match-head-commit pins the head", check_head_pin)
R3 = Requirement("G1.R3", "PR comments read after the newest", check_comments_read)
R4 = Requirement("G1.R4", "advisor after the last push", check_advisor)
R5 = Requirement("G1.R5", "shipping playbook read since compaction", check_playbook_read)
R6 = Requirement("G1.R6", "the user authorized landing", check_authority, escapable=False)
REQUIREMENTS = (R1, R2, R3, R4, R5, R6)


def _subject(c: MergeCtx) -> str:
    pr = c.pr.value
    where = f"{pr.repo}#{pr.number} @{pr.head_sha[:12]}" if pr else (c.merge.selector.text if c.merge.selector else "current branch")
    return f"{where}: `{c.merge.text}`"


class MergeGate:
    name = "G1"
    trigger_literal = TRIGGER

    def subjects(self, hook: HookCall) -> Tuple[MergeCall, ...]:
        return find_merges(hook)

    def decide(self, subjects: Sequence[MergeCall], session: Loaded[Session], env: Env) -> Tuple[Decision, ...]:
        escapes: Mapping = (
            collect_escapes((d.line, ledger.where(d.stamp)) for d, ledger in session.value.declared())
            if session.value
            else {}
        )
        decisions = []
        for merge in subjects:
            ctx = MergeCtx(merge, gather_pr(merge, env), session)
            decisions.append(adjudicate(self.name, _subject(ctx), REQUIREMENTS, ctx, escapes))
        return tuple(decisions)


GATE = MergeGate()

from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from core import Deadline, RunFailed, Runner, Unavailable

GH_CALL_TIMEOUT_S = 12.0


class Surface(enum.Enum):
    ISSUE = "issue"
    REVIEW = "review"
    INLINE = "inline"


@dataclass(frozen=True)
class Comment:
    id: str
    url: str
    surface: Surface
    author: str
    created_at: datetime
    changed_at: datetime
    body: str


@dataclass(frozen=True)
class PrFacts:
    repo: str
    number: int
    head_sha: str
    state: str
    comments: Tuple[Comment, ...]


class FactsUnavailable(Unavailable):
    pass


_FRACTION = re.compile(r"\.(\d+)")


def parse_ts(text: str) -> datetime:
    """ISO 8601 from GitHub or a transcript, with or without fractional seconds. Python 3.9's fromisoformat
    accepts neither `Z` nor fractions that are not 3 or 6 digits."""
    text = _FRACTION.sub(lambda m: "." + (m.group(1) + "000000")[:6], text.replace("Z", "+00:00"), count=1)
    ts = datetime.fromisoformat(text)
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def decode_concatenated(text: str) -> List[object]:
    """`gh api --paginate` prints one JSON array per page, back to back."""
    dec = json.JSONDecoder()
    out: List[object] = []
    i = 0
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            return out
        value, i = dec.raw_decode(text, i)
        out.extend(value if isinstance(value, list) else [value])


_PR_URL = re.compile(r"https?://[^/]+/([^/]+/[^/]+)/pull/(\d+)")
_SHA40 = re.compile(r"[0-9a-f]{40}")


def _comment(raw: dict, surface: Surface) -> Optional[Comment]:
    created = raw.get("submitted_at") if surface is Surface.REVIEW else raw.get("created_at")
    if not created:
        return None  # a pending review has no submission time and nobody else can see it
    created_at = parse_ts(created)
    updated = raw.get("updated_at")
    return Comment(
        id=str(raw["id"]),
        url=raw.get("html_url") or "",
        surface=surface,
        author=(raw.get("user") or {}).get("login") or "",
        created_at=created_at,
        changed_at=max(created_at, parse_ts(updated)) if updated else created_at,
        body=raw.get("body") or "",
    )


class GhCli:
    def __init__(self, run: Runner, deadline: Deadline) -> None:
        self._run = run
        self._deadline = deadline

    def _json(self, argv: List[str], workdir: Path) -> List[object]:
        remaining = self._deadline.remaining()
        if remaining < 1:
            raise FactsUnavailable("ran out of time before asking GitHub", "run the merge again")
        try:
            out = self._run(["gh", *argv], workdir, min(GH_CALL_TIMEOUT_S, remaining))
        except RunFailed as exc:
            raise FactsUnavailable(str(exc), "check `gh auth status` and the network, then run the merge again") from exc
        try:
            return decode_concatenated(out)
        except ValueError as exc:
            raise FactsUnavailable(f"`gh {' '.join(argv[:2])}` printed something that is not JSON: {exc}") from exc

    def fetch(self, selector: Optional[str], repo: Optional[str], workdir: Path) -> PrFacts:
        view_argv = ["pr", "view", *([selector] if selector else []), *(["-R", repo] if repo else [])]
        view = self._json([*view_argv, "--json", "number,url,headRefOid,state"], workdir)
        try:
            v = view[0]
            m = _PR_URL.match(v["url"])
            head = str(v["headRefOid"]).lower()
            if not m or not _SHA40.fullmatch(head):
                raise ValueError(f"unexpected pr view output {v!r}")
            full, number = m.group(1), int(m.group(2))
            comments = [
                c
                for path, surface in (
                    (f"repos/{full}/issues/{number}/comments", Surface.ISSUE),
                    (f"repos/{full}/pulls/{number}/reviews", Surface.REVIEW),
                    (f"repos/{full}/pulls/{number}/comments", Surface.INLINE),
                )
                for raw in self._json(["api", path, "--paginate"], workdir)
                for c in [_comment(raw, surface)]
                if c is not None
            ]
            return PrFacts(full, number, head, str(v["state"]), tuple(sorted(comments, key=lambda c: c.created_at)))
        except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
            raise FactsUnavailable(f"could not read gh output: {exc!r}") from exc


def stack_prs(run: Runner, deadline: Deadline, workdir: Path) -> List[Tuple[int, str]]:
    remaining = deadline.remaining()
    if remaining < 1:
        raise FactsUnavailable("ran out of time before asking gh stack", "run the merge again")
    try:
        view = json.loads(run(["gh", "stack", "view", "--json"], workdir, min(GH_CALL_TIMEOUT_S, remaining)))
        out = []
        for branch in view["branches"]:
            pr = branch.get("pr")
            if branch.get("isMerged") or not pr or pr.get("state") == "MERGED":
                continue
            m = _PR_URL.match(pr["url"])
            if not m:
                raise ValueError(f"unexpected PR url {pr['url']!r}")
            out.append((int(pr["number"]), m.group(1)))
        return out
    except RunFailed as exc:
        raise FactsUnavailable(str(exc), "run the merge from a checkout of the stack, or check `gh auth status`") from exc
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise FactsUnavailable(f"could not read `gh stack view --json`: {exc!r}") from exc

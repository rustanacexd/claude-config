import glob
import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from support import env, failed_ids, forbidden_runner
from core import RunFailed
import hook
from github import decode_concatenated, parse_ts

CASES = Path.home() / ".local/share/claude-gates/replay/cases.json"
REPLAY_TOOL_ID = "toolu_replay_merge"


class RecordedGh:
    FILES = (("issues/{n}/comments", "issue_comments.json", "issue"), ("pulls/{n}/reviews", "reviews.json", "review"),
             ("pulls/{n}/comments", "inline.json", "inline"))

    def __init__(self, fixture: Path, cut: datetime, extra: List[dict]) -> None:
        self.fixture, self.cut, self.extra = fixture, cut, extra
        self.view = json.loads((fixture / "pr_view.json").read_text())

    def __call__(self, argv, cwd, timeout):
        if list(argv[1:3]) == ["pr", "view"]:
            return json.dumps(self.view)
        for pattern, name, surface in self.FILES:
            if argv[2].endswith(pattern.format(n=self.view["number"])):
                rows = decode_concatenated((self.fixture / name).read_text())
                rows += [self._rest(c) for c in self.extra if c["surface"] == surface]
                return json.dumps([r for r in map(self._as_of_cut, rows) if r is not None])
        raise AssertionError(f"unexpected gh call {argv}")

    def _rest(self, c: dict) -> dict:
        url = f"{self.view['url']}#issuecomment-{c['id']}"
        return {"id": c["id"], "html_url": url, "user": {"login": c["user"]}, "created_at": c["created_at"],
                "updated_at": c["created_at"], "body": c["body"]}

    def _as_of_cut(self, row: dict) -> Optional[dict]:
        created = row.get("submitted_at") or row.get("created_at")
        if not created or parse_ts(created) > self.cut:
            return None
        if row.get("updated_at") and parse_ts(row["updated_at"]) > self.cut:
            row = {**row, "updated_at": created}
        return row


def _insert_by_time(records: List[dict], new: dict) -> None:
    at = parse_ts(new["timestamp"])
    i = next((k for k, r in enumerate(records) if r.get("timestamp") and parse_ts(r["timestamp"]) > at), len(records))
    records.insert(i, new)


def _synthetic(spec: dict, n: int) -> List[dict]:
    if spec["kind"] == "advisor":
        return [{"type": "assistant", "isSidechain": False, "timestamp": spec["at"],
                 "message": {"role": "assistant", "content": [{"type": "server_tool_use", "id": f"srvtoolu_replay{n}", "name": "advisor", "input": {}}]}}]
    tid = f"toolu_replay{n}"
    return [{"type": "assistant", "isSidechain": False, "timestamp": spec["at"],
             "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": spec["command"]}}]}},
            {"type": "user", "isSidechain": False, "timestamp": spec["at"],
             "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": spec["result"], "is_error": False}]}}]


def _write(path: Path, records: List[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    return path


class RecordedGit:
    def __init__(self, files: Optional[List[str]]) -> None:
        self.files = files

    def __call__(self, argv, cwd, timeout):
        if list(argv[:2]) == ["git", "symbolic-ref"]:
            return "origin/main\n"
        if self.files is None:
            raise RunFailed("this replay case records no diff")
        return "".join(f + "\n" for f in self.files)


def _bash_call(rec: dict) -> dict:
    (call,) = [c for c in rec["message"]["content"] if c.get("type") == "tool_use" and c.get("name") == "Bash"]
    return call


def _copy_agents(src: Path, tmp: Path, cut: datetime, skip: Optional[Path]) -> None:
    for agent_file in src.with_suffix("").glob("subagents/agent-*.jsonl"):
        if agent_file != skip:
            kept = [r for r in map(json.loads, agent_file.read_text().splitlines()) if r.get("timestamp") and parse_ts(r["timestamp"]) <= cut]
            if kept:
                _write(tmp / src.stem / "subagents" / agent_file.name, kept)


def replay(case: dict, table: dict, tmp: Path, line: Optional[int] = None, agent_file: Optional[str] = None):
    (src,) = glob.glob(f"{table['projects']}/{case['project']}/{case['session']}*.jsonl")
    src = Path(src)
    line = line or case["line"]
    agent_file = agent_file or case.get("agent_file")
    acting = src.with_suffix("") / "subagents" / agent_file if agent_file else src
    acting_lines = acting.read_text().splitlines()
    gated_rec = json.loads(acting_lines[line - 1])
    gated = _bash_call(gated_rec)
    cut = parse_ts(gated_rec["timestamp"])
    command = gated["input"]["command"]
    payload = {"session_id": src.stem, "cwd": gated_rec.get("cwd", "/"), "hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": command}, "tool_use_id": gated["id"]}

    if agent_file:
        root_records = [r for r in map(json.loads, src.read_text().splitlines()) if not r.get("timestamp") or parse_ts(r["timestamp"]) <= cut]
        _write(tmp / src.stem / "subagents" / agent_file, [json.loads(x) for x in acting_lines[:line]])
        meta = json.loads(acting.with_name(agent_file.replace(".jsonl", ".meta.json")).read_text())
        payload.update(agent_id=acting.stem[len("agent-"):], agent_type=meta.get("agentType", "replay"))
        _copy_agents(src, tmp, cut, acting)
    else:
        through = acting_lines[:line]
        root_records = [json.loads(x) for x in (through[:-1] if case.get("actor") else through)]
        _copy_agents(src, tmp, cut, None)
    for n, spec in enumerate(case.get("insert", [])):
        for rec in _synthetic(spec, n):
            _insert_by_time(root_records, rec)
    payload["transcript_path"] = str(_write(tmp / src.name, root_records))

    if case.get("actor"):
        metas = [m for m in src.with_suffix("").glob("subagents/agent-*.meta.json")
                 if re.search(case["actor"], json.loads(m.read_text()).get("description", ""))]
        (meta,) = metas
        actor_file = meta.with_name(meta.name.replace(".meta.json", ".jsonl"))
        sub = [r for r in map(json.loads, actor_file.read_text().splitlines()) if r.get("timestamp") and parse_ts(r["timestamp"]) <= cut]
        sub.append({**gated_rec, "isSidechain": True, "message": {**gated_rec["message"], "content": [{**gated, "id": REPLAY_TOOL_ID}]}})
        _write(tmp / src.stem / "subagents" / actor_file.name, sub)
        payload.update(tool_use_id=REPLAY_TOOL_ID, agent_id=actor_file.stem[len("agent-"):], agent_type="replay")

    gh = RecordedGh(Path(table["fixtures"]) / case["fixture"], cut, case.get("add_comments", [])) if case.get("fixture") else forbidden_runner
    git = RecordedGit(case.get("git_files"))
    return hook.run(json.dumps(payload), env(lambda argv, cwd, timeout: (git if argv[0] == "git" else gh)(argv, cwd, timeout)))


def bash_points(case: dict, table: dict):
    (src,) = glob.glob(f"{table['projects']}/{case['project']}/{case['session']}*.jsonl")
    for path in (Path(src), *sorted(Path(src).with_suffix("").glob("subagents/agent-*.jsonl"))):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if '"Bash"' in line and '"tool_use"' in line:
                rec = json.loads(line)
                if rec.get("type") == "assistant" and any(c.get("name") == "Bash" for c in rec["message"]["content"] if isinstance(c, dict)):
                    yield n, (None if path == Path(src) else path.name)


def _rid(r) -> str:
    return f"G1.R{r}" if isinstance(r, int) else r


@unittest.skipUnless(CASES.exists(), f"local replay table {CASES} is absent")
class ReplayLocal(unittest.TestCase):
    def test_cases(self):
        table = json.loads(CASES.read_text())
        registered = {gate.name for gate in hook.gates()}
        for case in table["cases"]:
            if case.get("silent") or not {_rid(r).split(".")[0] for r in case["must_fail"]} <= registered:
                continue
            with self.subTest(case["id"]), tempfile.TemporaryDirectory() as tmp:
                outcome = replay(case, table, Path(tmp))
                failed = failed_ids(outcome)
                must = {_rid(r) for r in case["must_fail"]}
                may = {_rid(r) for r in case["may_fail"]}
                if not must:
                    self.assertEqual((outcome.exit_code, failed), (0, frozenset()), outcome.stderr)
                    continue
                self.assertEqual(outcome.exit_code, 2)
                self.assertTrue(must <= failed <= must | may, f"failed {sorted(failed)}\n{outcome.stderr}")

    def test_silent_sessions_stay_silent_at_every_bash_call(self):
        table = json.loads(CASES.read_text())
        for case in table["cases"]:
            if not case.get("silent"):
                continue
            points = list(bash_points(case, table))
            for line, agent_file in points:
                with self.subTest(case["id"], line=line, agent=agent_file), tempfile.TemporaryDirectory() as tmp:
                    outcome = replay(case, table, Path(tmp), line, agent_file)
                    self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()

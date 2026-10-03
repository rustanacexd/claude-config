import glob
import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from support import env, failed_ids, forbidden_runner
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


def replay(case: dict, table: dict, tmp: Path):
    (src,) = glob.glob(f"{table['projects']}/{case['project']}/{case['session']}*.jsonl")
    src = Path(src)
    lines = src.read_text().splitlines()
    merge_rec = json.loads(lines[case["line"] - 1])
    (merge,) = [c for c in merge_rec["message"]["content"] if c.get("type") == "tool_use" and c.get("name") == "Bash"]
    cut = parse_ts(merge_rec["timestamp"])
    command = merge["input"]["command"]

    through_merge = lines[: case["line"]]
    root_lines = through_merge[:-1] if case.get("actor") else through_merge
    records = [json.loads(line) for line in root_lines]
    for n, spec in enumerate(case.get("insert", [])):
        for rec in _synthetic(spec, n):
            _insert_by_time(records, rec)
    root = _write(tmp / src.name, records)

    payload = {"session_id": src.stem, "transcript_path": str(root), "cwd": merge_rec.get("cwd", "/"),
               "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command},
               "tool_use_id": merge["id"]}
    if case.get("actor"):
        metas = [m for m in src.with_suffix("").glob("subagents/agent-*.meta.json")
                 if re.search(case["actor"], json.loads(m.read_text()).get("description", ""))]
        (meta,) = metas
        agent_file = meta.with_name(meta.name.replace(".meta.json", ".jsonl"))
        sub = [r for r in map(json.loads, agent_file.read_text().splitlines()) if r.get("timestamp") and parse_ts(r["timestamp"]) <= cut]
        sub.append({**merge_rec, "isSidechain": True, "message": {**merge_rec["message"], "content": [{**merge, "id": REPLAY_TOOL_ID}]}})
        _write(tmp / src.stem / "subagents" / agent_file.name, sub)
        payload.update(tool_use_id=REPLAY_TOOL_ID, agent_id=agent_file.stem[len("agent-"):], agent_type="replay")

    run = RecordedGh(Path(table["fixtures"]) / case["fixture"], cut, case.get("add_comments", [])) if case["fixture"] else forbidden_runner
    return hook.run(json.dumps(payload), env(run))


@unittest.skipUnless(CASES.exists(), f"local replay table {CASES} is absent")
class ReplayLocal(unittest.TestCase):
    def test_cases(self):
        table = json.loads(CASES.read_text())
        for case in table["cases"]:
            with self.subTest(case["id"]), tempfile.TemporaryDirectory() as tmp:
                outcome = replay(case, table, Path(tmp))
                failed = failed_ids(outcome)
                must = {f"G1.R{n}" for n in case["must_fail"]}
                may = {f"G1.R{n}" for n in case["may_fail"]}
                if not must:
                    self.assertEqual((outcome.exit_code, failed), (0, frozenset()), outcome.stderr)
                    continue
                self.assertEqual(outcome.exit_code, 2)
                self.assertTrue(must <= failed <= must | may, f"failed {sorted(failed)}\n{outcome.stderr}")


if __name__ == "__main__":
    unittest.main()

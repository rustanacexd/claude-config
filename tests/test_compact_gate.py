import json
import tempfile
import unittest
from pathlib import Path

from support import Transcript, at, env, forbidden_runner
from test_stop_gates import files
import hook
from core import Mode


def compact_payload(path: Path, source: str = "compact") -> str:
    return json.dumps({"session_id": "sess-1", "transcript_path": str(path), "cwd": "/work", "hook_event_name": "SessionStart",
                       "source": source})


def compacted_session(tmp: Path, n_tasks: int = 0) -> Path:
    playbook, _, _ = files(tmp)
    t = Transcript().slash("pstack:poteto-mode", at(0), "add the feature")
    t.read(playbook, at(1))
    t.task("1. `how` over the affected subsystem.", at(2))
    t.task("2. Delegate the code to a subagent with its own worktree.", at(2, 1))
    t.task("skip: G3.R4 the advisor tool is offline", at(2, 2))
    t.task_update("1", "completed", at(3))
    t.tool("Write", {"file_path": "/tmp/run/todo.md", "content": "- [ ] step"}, at(3, 30), "ok")
    for n in range(n_tasks):
        t.task(f"filler task number {n} with a long subject to fill the cap quickly", at(4, n % 60))
    t.compact(at(5))
    return t.write(tmp / "session.jsonl")


class CompactReinject(unittest.TestCase):
    def context(self, outcome):
        self.assertEqual((outcome.exit_code, outcome.stderr), (0, ""))
        return json.loads(outcome.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_lists_playbooks_open_tasks_todo_files_and_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.context(hook.run(compact_payload(compacted_session(Path(tmp))), env(forbidden_runner)))
            self.assertIn(f"Playbooks read:\n- {Path(tmp)}/skills/poteto-mode/playbooks/feature.md", text)
        self.assertIn("- #2 2. Delegate the code", text)
        self.assertNotIn("#1 1. `how`", text)
        self.assertIn("Todo files:\n- /tmp/run/todo.md", text)
        self.assertIn("Declared skips:\n- skip: G3.R4 the advisor tool is offline", text)
        self.assertIn("G1 accepts only a full read of playbooks/shipping.md made after this compaction", text)
        self.assertNotIn("Workflow gates allowed this", text)

    def test_capped_at_2000_characters_with_the_instruction_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.context(hook.run(compact_payload(compacted_session(Path(tmp), n_tasks=80)), env(forbidden_runner)))
        self.assertLessEqual(len(text), 2000)
        self.assertTrue(text.startswith("poteto-mode state from before this compaction"))
        self.assertTrue(text.endswith("cut at 2000 characters"), text[-80:])

    def test_silent_unless_compact_and_poteto(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = compacted_session(Path(tmp))
            self.assertEqual(hook.run(compact_payload(path, "startup"), env(forbidden_runner)).stdout, "")
            plain = Transcript().user("hello", at(0)).compact(at(1)).write(Path(tmp) / "plain.jsonl")
            self.assertEqual(hook.run(compact_payload(plain), env(forbidden_runner)).stdout, "")

    def test_never_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = hook.run(compact_payload(compacted_session(Path(tmp))), env(forbidden_runner, Mode.BLOCK))
        self.assertEqual(outcome.exit_code, 0)


if __name__ == "__main__":
    unittest.main()

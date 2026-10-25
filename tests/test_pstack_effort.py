import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import install


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks/pstack_effort.py"


class EffortHookTests(unittest.TestCase):
    def call_hook(self, event):
        result = subprocess.run(
            [sys.executable, str(HOOK)], input=json.dumps(event),
            text=True, capture_output=True, check=True,
        )
        return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout else None

    def test_claude_uses_live_effort_and_preserves_model(self):
        for level in ("low", "medium", "high", "xhigh", "max"):
            with self.subTest(level=level):
                output = self.call_hook({
                    "tool_name": "Agent", "effort": {"level": level},
                    "tool_input": {"model": "fable", "prompt": "probe", "effort": "low"},
                })
                self.assertEqual(output["updatedInput"], {
                    "model": "fable", "prompt": "probe", "effort": level,
                })
                self.assertNotIn("permissionDecision", output)

    def test_missing_claude_effort_blocks_instead_of_guessing(self):
        output = self.call_hook({"tool_name": "Agent", "tool_input": {"model": "opus"}})
        self.assertEqual(output["permissionDecision"], "deny")

    def test_unknown_effort_blocks(self):
        output = self.call_hook({
            "tool_name": "Agent", "effort": {"level": "auto"}, "tool_input": {},
        })
        self.assertEqual(output["permissionDecision"], "deny")

    def test_other_tools_are_untouched(self):
        self.assertIsNone(self.call_hook({"tool_name": "Bash", "tool_input": {}}))

    def test_codex_reads_only_the_current_turn_and_latest_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "rollout.jsonl"
            rows = [
                {"type": "turn_context", "payload": {"turn_id": "old", "effort": "low"}},
                {"type": "turn_context", "payload": {"turn_id": "now", "effort": "medium"}},
                {"type": "turn_context", "payload": {"turn_id": "now", "effort": "high"}},
                {"type": "response_item", "payload": {"effort": "low"}},
            ]
            transcript.write_text("\n".join(map(json.dumps, rows)) + '\n{"partial":')
            event = {
                "tool_name": "spawn_agent", "turn_id": "now", "transcript_path": str(transcript),
                "tool_input": {"model": "gpt-6-astra", "reasoning_effort": "low"},
            }
            output = self.call_hook(event)
            self.assertEqual(output["updatedInput"], {"model": "gpt-6-astra", "reasoning_effort": "high"})
            self.assertEqual(output["permissionDecision"], "allow")
            event["tool_name"] = "collaborationspawn_agent"
            self.assertEqual(self.call_hook(event)["updatedInput"]["reasoning_effort"], "high")
            event["turn_id"] = "missing"
            self.assertEqual(self.call_hook(event)["permissionDecision"], "deny")

    def test_unreadable_codex_transcript_blocks(self):
        output = self.call_hook({
            "tool_name": "spawn_agent", "turn_id": "now", "transcript_path": "/missing/rollout",
            "tool_input": {"model": "gpt-6.1-sol"},
        })
        self.assertEqual(output["permissionDecision"], "deny")


class InstallationTests(unittest.TestCase):
    def test_migrates_model_efforts_preserves_other_settings_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(install, "CLAUDE", Path(tmp)):
            path = Path(tmp) / "settings.json"
            original = {
                "modelSettings": {
                    "claude-fable-5-1": {"effortLevel": "high", "autoCompactWindow": 200000},
                    "claude-opus-5-5": {"effortLevel": "medium"},
                    "unrelated-model": {"effortLevel": "low"},
                },
                "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": "echo keep"}]}]},
            }
            path.write_text(json.dumps(original))
            with contextlib.redirect_stdout(io.StringIO()):
                install.claude_settings()
            first = path.read_bytes()
            current = json.loads(first)
            self.assertEqual(current["modelSettings"], {
                "claude-fable-5-1": {"autoCompactWindow": 200000},
                "unrelated-model": {"effortLevel": "low"},
            })
            self.assertEqual(current["hooks"]["PreToolUse"][0], original["hooks"]["PreToolUse"][0])
            self.assertIn("pstack_effort.py", json.dumps(current["hooks"]))
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                install.claude_settings()
            self.assertEqual(path.read_bytes(), first)
            self.assertEqual(stdout.getvalue(), "")

    def test_codex_hook_preserves_existing_hooks_and_trust(self):
        settings = {"hooks": {"state": {"existing": {"trusted_hash": "keep"}}, "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo keep"}]},
        ]}}
        install.agent_effort_hook(settings, Path("/codex-home"))
        first = json.dumps(settings)
        install.agent_effort_hook(settings, Path("/codex-home"))
        self.assertEqual(json.dumps(settings), first)
        self.assertEqual(settings["hooks"]["state"]["existing"]["trusted_hash"], "keep")
        self.assertEqual(len(settings["hooks"]["PreToolUse"]), 2)


if __name__ == "__main__":
    unittest.main()

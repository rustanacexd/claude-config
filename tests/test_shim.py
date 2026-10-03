import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import GATES
import hook

SHIM = GATES / "gate.sh"


def run_shim(command: str, python_exit=None, args=("PreToolUse", "Bash"), home: str = ""):
    with tempfile.TemporaryDirectory() as tmp:
        bindir, marker = Path(tmp), Path(tmp) / "ran"
        if python_exit is not None:
            fake = bindir / "python3"
            fake.write_text(f"#!/bin/sh\ncat >/dev/null\ntouch {marker}\nexit {python_exit}\n")
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        path = f"{bindir}:/bin" if python_exit is None else f"{bindir}:/usr/bin:/bin"  # /usr/bin holds a real python3
        proc = subprocess.run(["/bin/sh", str(SHIM), *args], input=stdin, text=True, capture_output=True, env={"PATH": path, "HOME": home})
        return proc.returncode, marker.exists(), proc.stdout


class Shim(unittest.TestCase):
    def test_settings_can_run_it_directly(self):
        self.assertTrue(os.access(SHIM, os.X_OK))

    def test_a_gates_off_file_under_home_allows_every_event_without_starting_python(self):
        with tempfile.TemporaryDirectory() as home:
            off = Path(home) / ".claude" / "gates.off"
            off.parent.mkdir()
            for args, command in ((("Stop",), "x"), (("PreToolUse", "Bash"), "gh pr merge 1"), (("TaskCompleted",), "x")):
                with self.subTest(args):
                    self.assertEqual(run_shim(command, python_exit=2, args=args, home=home)[:2], (2, True))
                    off.touch()
                    self.assertEqual(run_shim(command, python_exit=2, args=args, home=home)[:2], (0, False))
                    off.unlink()

    def test_bash_without_a_trigger_exits_0_without_starting_python(self):
        self.assertEqual(run_shim("ls -la", python_exit=2)[:2], (0, False))

    def test_every_trigger_literal_starts_python(self):
        literals = {lit for gate in hook.gates() if "Bash" in gate.tools for lit in gate.trigger_literals}
        for literal in literals:
            with self.subTest(literal):
                self.assertEqual(run_shim(f"x {literal} y", python_exit=0)[:2], (0, True))

    def test_other_tools_and_events_always_start_python(self):
        for args in (("PreToolUse",), ("Stop",), ("TaskCompleted",), ("SessionStart",)):
            with self.subTest(args):
                self.assertTrue(run_shim("ls", python_exit=0, args=args)[1])

    def test_python_verdict_passes_through(self):
        self.assertEqual(run_shim("gh pr merge 1", python_exit=2)[:2], (2, True))
        self.assertEqual(run_shim("x", python_exit=2, args=("Stop",))[:2], (2, True))

    def test_any_other_failure_blocks_a_tool_or_task_event(self):
        self.assertEqual(run_shim("gh pr merge 1", python_exit=1)[:2], (2, True))
        self.assertEqual(run_shim("gh pr merge 1", python_exit=None)[0], 2)
        self.assertEqual(run_shim("x", python_exit=1, args=("TaskCompleted",))[0], 2)

    def test_any_other_failure_allows_stop_and_session_start(self):
        for event in ("Stop", "SessionStart"):
            with self.subTest(event):
                code, _, out = run_shim("x", python_exit=None, args=(event,))
                self.assertEqual(code, 0)
                self.assertIn("crashed (exit 127)", json.loads(out)["systemMessage"])


if __name__ == "__main__":
    unittest.main()

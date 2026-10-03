import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import GATES

SHIM = GATES / "g1.sh"


def run_shim(command: str, python_exit=None):
    with tempfile.TemporaryDirectory() as tmp:
        bindir, marker = Path(tmp), Path(tmp) / "ran"
        if python_exit is not None:
            fake = bindir / "python3"
            fake.write_text(f"#!/bin/sh\ncat >/dev/null\ntouch {marker}\nexit {python_exit}\n")
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        path = f"{bindir}:/bin" if python_exit is None else f"{bindir}:/usr/bin:/bin"  # /usr/bin holds a real python3
        proc = subprocess.run(["/bin/sh", str(SHIM)], input=stdin, text=True, capture_output=True, env={"PATH": path})
        return proc.returncode, marker.exists()


class Shim(unittest.TestCase):
    def test_non_merge_exits_0_without_starting_python(self):
        self.assertEqual(run_shim("ls -la", python_exit=2), (0, False))

    def test_python_verdict_passes_through(self):
        self.assertEqual(run_shim("gh pr merge 1", python_exit=0), (0, True))
        self.assertEqual(run_shim("gh pr merge 1", python_exit=2), (2, True))

    def test_any_other_failure_blocks(self):
        self.assertEqual(run_shim("gh pr merge 1", python_exit=1), (2, True))
        self.assertEqual(run_shim("gh pr merge 1", python_exit=None)[0], 2)


if __name__ == "__main__":
    unittest.main()

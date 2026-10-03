import io
import json
import unittest
from pathlib import Path

from support import env, forbidden_runner
import hook
from core import (
    Check, Env, Event, MalformedHook, Mode, Requirement, adjudicate, parse_hook_call, render,
)

HARD = Requirement("G9.R1", "hard", lambda c: Check.failed("hard failed", "fix it"))
SOFT = Requirement("G9.R2", "soft", lambda c: Check.failed("soft failed", "consider it"), advisory=True)


def decision(*reqs, gate="G9"):
    return adjudicate(gate, "subject", reqs, None, {})


def common(event, **extra):
    return json.dumps({"session_id": "s", "transcript_path": "/t.jsonl", "cwd": "/w", "hook_event_name": event, **extra})


class ParseHookCall(unittest.TestCase):
    def test_each_event_carries_its_fields(self):
        stop = parse_hook_call(common("Stop", stop_hook_active=True, last_assistant_message="done"))
        self.assertEqual((stop.event, stop.stop_hook_active, stop.last_assistant_message), (Event.STOP, True, "done"))
        task = parse_hook_call(common("TaskCompleted", task_id="3", task_subject="run deslop"))
        self.assertEqual((task.task_id, task.task_subject, task.task_description), ("3", "run deslop", ""))
        start = parse_hook_call(common("SessionStart", source="compact"))
        self.assertEqual(start.source, "compact")
        write = parse_hook_call(common("PreToolUse", tool_name="Write", tool_input={"file_path": "/a", "content": "x"},
                                       agent_id="a1", agent_type="pstack:poteto-agent"))
        self.assertEqual((write.tool_input["file_path"], write.command, write.agent_type), ("/a", "", "pstack:poteto-agent"))

    def test_rejects_unknown_events_and_missing_transcripts(self):
        for raw in (common("Notification"), json.dumps({"hook_event_name": "Stop"}), common("PreToolUse", tool_input="ls")):
            with self.subTest(raw), self.assertRaises(MalformedHook):
                parse_hook_call(raw)


class Render(unittest.TestCase):
    def test_advisory_never_blocks(self):
        for event in Event:
            with self.subTest(event):
                outcome = render(event, [decision(SOFT)], env(forbidden_runner, Mode.BLOCK))
                self.assertEqual(outcome.exit_code, 0)
                self.assertIn("ADVISORY G9.R2 soft: soft failed", outcome.stdout)

    def test_a_block_also_reports_advisories(self):
        outcome = render(Event.PRE_TOOL_USE, [decision(HARD), decision(SOFT, gate="G8")], env(forbidden_runner))
        self.assertEqual(outcome.exit_code, 2)
        self.assertIn("FAIL G9.R1", outcome.stderr)
        self.assertIn("ADVISORY G9.R2 soft", outcome.stderr)

    def test_each_event_uses_its_channel(self):
        warn = env(forbidden_runner, Mode.WARN)
        cases = (
            (Event.PRE_TOOL_USE, ("hookSpecificOutput", "additionalContext")),
            (Event.SESSION_START, ("hookSpecificOutput", "additionalContext")),
            (Event.STOP, ("systemMessage",)),
            (Event.TASK_COMPLETED, ("systemMessage",)),
        )
        for event, path in cases:
            with self.subTest(event):
                outcome = render(event, [decision(HARD)], warn)
                value = json.loads(outcome.stdout)
                for key in path:
                    value = value[key]
                self.assertEqual(outcome.exit_code, 0)
                self.assertIn("NOT blocked", value)

    def test_blocking_events_exit_2_and_session_start_never_does(self):
        block = env(forbidden_runner, Mode.BLOCK)
        for event in (Event.PRE_TOOL_USE, Event.STOP, Event.TASK_COMPLETED):
            with self.subTest(event):
                self.assertEqual(render(event, [decision(HARD)], block).exit_code, 2)
        self.assertEqual(render(Event.SESSION_START, [decision(HARD)], block).exit_code, 0)


class PerGateMode(unittest.TestCase):
    def test_a_gate_mode_overrides_the_global_mode(self):
        e = Env.from_environ({"GATES_MODE": "warn", "GATES_MODE_G9": "block"}, Event.PRE_TOOL_USE)
        self.assertEqual((e.mode_for("G9"), e.mode_for("G1")), (Mode.BLOCK, Mode.WARN))
        self.assertEqual(Env.from_environ({}, Event.STOP).mode_for("G1"), Mode.BLOCK)
        outcome = render(Event.PRE_TOOL_USE, [decision(HARD), decision(HARD, gate="G1")], e)
        self.assertIn("G9 gate", outcome.stderr)
        self.assertNotIn("G1 gate", outcome.stderr.split("Blocked")[1].split("To skip")[0])

    def test_deadline_is_set_per_event(self):
        pre = Env.from_environ({}, Event.PRE_TOOL_USE).deadline.remaining()
        stop = Env.from_environ({}, Event.STOP).deadline.remaining()
        self.assertTrue(39 < pre <= 40 and 6 < stop <= 7, (pre, stop))


class CrashPolicy(unittest.TestCase):
    def crash(self, event, raw):
        stdout, stderr = io.StringIO(), io.StringIO()
        code = hook.main(io.StringIO(raw), stdout, stderr, {}, event)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_stop_and_session_start_allow_on_a_crash(self):
        for event in ("Stop", "SessionStart"):
            with self.subTest(event):
                code, out, _ = self.crash(event, "not json")
                self.assertEqual(code, 0)
                self.assertIn("crashed", json.loads(out)["systemMessage"])

    def test_tool_and_task_events_block_on_a_crash(self):
        for event in ("PreToolUse", "TaskCompleted", "NoSuchEvent"):
            with self.subTest(event):
                code, _, err = self.crash(event, "not json")
                self.assertEqual(code, 2)
                self.assertIn("crashed", err)


class Dispatch(unittest.TestCase):
    def test_bash_gates_ignore_other_tools_and_events(self):
        for raw in (common("Stop", last_assistant_message="gh pr create"),
                    common("PreToolUse", tool_name="Write", tool_input={"file_path": "/a", "content": "gh pr create"})):
            with self.subTest(raw):
                self.assertEqual(hook.run(raw, env(forbidden_runner)).exit_code, 0)

    def test_the_shell_literals_are_the_bash_gates_literals(self):
        shim = (Path(hook.__file__).parent / "gate.sh").read_text()
        literals = {g for gate in hook.gates() if "Bash" in gate.tools for g in gate.trigger_literals}
        case_line = next(line for line in shim.splitlines() if '*"gh pr merge"*' in line)
        self.assertEqual(set(case_line.split('"')[1::2]), literals)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, Tuple
from unittest import mock

from support import Piece, Transcript, at, env, flagged_ids, forbidden_runner, said
import evidence
import hook
from core import Mode
from g4_task import named_skills
from test_agent_evidence import spawn

AGENT_ID = "toolu_agent"
SKILL_ID = "toolu_skill"


TASK_ID = "7"


@dataclass(frozen=True)
class TaskCase:
    pieces: Tuple[Tuple[str, Piece], ...]
    subject: str = "Run /deslop and no-comments on the diff"
    description: str = "Before commit"
    sub_pieces: Tuple[Tuple[str, Piece], ...] = ()


TASK_GREEN = TaskCase(
    pieces=(("poteto", lambda t: t.slash("pstack:poteto-mode", at(0), "build it")),
            ("task", lambda t: t.task("Run /deslop and no-comments on the diff", at(1))),
            ("no_comments", lambda t: t.skill("pstack:no-comments", at(3)))),
    sub_pieces=(("deslop", lambda t: t.skill("pstack:deslop", at(2))),),
)


def run_task(case: TaskCase, tmp: Path, mode: Mode = Mode.BLOCK, path: Optional[Path] = None):
    t = Transcript()
    for _, piece in case.pieces:
        piece(t)
    path = path or t.write(tmp / "session.jsonl")
    if case.sub_pieces:
        sub = Transcript()
        for _, piece in case.sub_pieces:
            piece(sub)
        sub.write(tmp / "session" / "subagents" / "agent-d1.jsonl")
    raw = json.dumps({"session_id": "sess-1", "transcript_path": str(path), "cwd": "/work", "hook_event_name": "TaskCompleted",
                      "task_id": TASK_ID, "task_subject": case.subject, "task_description": case.description})
    return hook.run(raw, env(forbidden_runner, mode))


def without(case, *names):
    return replace(case, pieces=tuple(p for p in case.pieces if p[0] not in names),
                   sub_pieces=tuple(p for p in case.sub_pieces if p[0] not in names))


TASK_MUTATIONS = (
    ("deslop never ran", without(TASK_GREEN, "deslop")),
    ("no-comments never ran", without(TASK_GREEN, "no_comments")),
    ("the task names /how and how never ran", replace(TASK_GREEN, subject="Trace it with /how first")),
    ("the task names the why skill and why never ran", replace(TASK_GREEN, description="use the why skill on the regression")),
    ("a playbook step names architect", replace(TASK_GREEN, subject="2. `architect` for parallel design exploration.")),
    ("the task names Deslop in title case", replace(without(TASK_GREEN, "deslop"), subject="Run Deslop on the diff")),
)


class TaskGate(unittest.TestCase):
    def test_green_allows_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_task(TASK_GREEN, Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_each_mutation_refuses_the_completion_with_g4_r1(self):
        for name, case in TASK_MUTATIONS:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                outcome = run_task(case, Path(tmp))
                self.assertEqual((outcome.exit_code, flagged_ids(outcome)), (2, frozenset({"G4.R1"})), outcome.stderr)

    def test_the_refusal_names_the_missing_skill_and_how_to_fix_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_task(without(TASK_GREEN, "deslop"), Path(tmp))
        self.assertIn("task #7 names deslop", outcome.stderr)
        self.assertIn("`pstack:deslop`", outcome.stderr)

    def test_bare_how_and_why_are_english_not_skills(self):
        self.assertEqual(named_skills("Explain how and why the timer drifts"), ())
        self.assertEqual(named_skills("run /how, the why skill, pstack:how"), ("how", "why"))
        self.assertEqual(named_skills("deslopped no-commentsy docs/how-to"), ())

    def test_a_skip_in_the_task_text_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_task(replace(without(TASK_GREEN, "deslop"), description="skip: one-line change"), Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stderr), (0, ""))

    def test_a_declared_skip_line_passes_and_is_echoed(self):
        case = replace(without(TASK_GREEN, "deslop"), pieces=without(TASK_GREEN, "deslop").pieces
                       + (("skip", lambda t: t.task("skip: G4.R1 the diff is docs only", at(4))),))
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_task(case, Path(tmp))
        self.assertEqual(outcome.exit_code, 0, outcome.stderr)
        self.assertIn("G4.R1 skipped: the diff is docs only", said(outcome))

    def test_warn_mode_reports_through_system_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_task(without(TASK_GREEN, "deslop"), Path(tmp), Mode.WARN)
        self.assertEqual(outcome.exit_code, 0)
        self.assertIn("FAIL G4.R1", json.loads(outcome.stdout)["systemMessage"])

    def test_a_session_without_poteto_is_never_parsed(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(evidence, "load_session", side_effect=AssertionError("parsed")):
            outcome = run_task(without(TASK_GREEN, "poteto", "deslop"), Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_a_task_naming_no_skill_never_reads_the_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_task(replace(TASK_GREEN, subject="Write the tests", description=""), Path(tmp), path=Path(tmp) / "missing.jsonl")
        self.assertEqual((outcome.exit_code, outcome.stderr), (0, ""))

    def test_an_unreadable_transcript_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_task(TASK_GREEN, Path(tmp), path=Path(tmp) / "missing.jsonl")
        self.assertEqual(outcome.exit_code, 2)
        self.assertIn("cannot verify", outcome.stderr)


def routing_payload(path: Path, tool: str, inp: dict, tool_use_id: str) -> str:
    return json.dumps({"session_id": "sess-1", "transcript_path": str(path), "cwd": "/work", "hook_event_name": "PreToolUse",
                       "tool_name": tool, "tool_input": inp, "tool_use_id": tool_use_id})


AGENT_INPUT = {"subagent_type": "general-purpose", "description": "d", "prompt": "p"}


@dataclass(frozen=True)
class RoutingCase:
    pieces: Tuple[Tuple[str, Piece], ...]
    tool: str = "Agent"
    inp: Optional[dict] = None
    own_record: bool = True


ROUTING_GREEN = RoutingCase(pieces=(
    ("poteto", lambda t: t.slash("pstack:poteto-mode", at(0), "build it")),
    ("earlier_message", lambda t: (spawn(t, at(1), "msg_1"), spawn(t, at(1, 5), "msg_1"))),
    ("sibling", lambda t: spawn(t, at(2), "msg_2")),
))


def run_routing(case: RoutingCase, tmp: Path, mode: Mode = Mode.BLOCK):
    t = Transcript()
    for _, piece in case.pieces:
        piece(t)
    tool_id = AGENT_ID if case.tool == "Agent" else SKILL_ID
    inp = case.inp or (AGENT_INPUT if case.tool == "Agent" else {"skill": "pstack:deslop"})
    if case.own_record:
        t.tool(case.tool, inp, at(3), None, tool_id=tool_id)
        t.records[-1]["message"]["id"] = "msg_2"
    return hook.run(routing_payload(t.write(tmp / "session.jsonl"), case.tool, inp, tool_id), env(forbidden_runner, mode))


def rplus(case, *pieces):
    return replace(case, pieces=case.pieces + pieces)


def rwithout(case, *names):
    return replace(case, pieces=tuple(p for p in case.pieces if p[0] not in names))


THIRD = rplus(ROUTING_GREEN, ("second_sibling", lambda t: spawn(t, at(2, 30), "msg_2")))
ROUTING_MUTATIONS = (
    ("a third Agent call in one message", frozenset({"G5.R1"}), THIRD),
    ("a third Agent call whose own record is not on disk yet", frozenset({"G5.R1"}), replace(THIRD, own_record=False)),
    ("the bundled babysit skill", frozenset({"G5.R2"}), replace(ROUTING_GREEN, tool="Skill", inp={"skill": "babysit"})),
    ("the plugin babysit skill", frozenset({"G5.R2"}), replace(ROUTING_GREEN, tool="Skill", inp={"skill": "pstack:babysit", "args": "42"})),
)


class RoutingGate(unittest.TestCase):
    def test_green_allows_silently(self):
        for case in (ROUTING_GREEN, replace(ROUTING_GREEN, tool="Skill")):
            with self.subTest(case.tool), tempfile.TemporaryDirectory() as tmp:
                outcome = run_routing(case, Path(tmp))
                self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_each_mutation_flags_exactly_its_requirement(self):
        for name, expected, case in ROUTING_MUTATIONS:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                outcome = run_routing(case, Path(tmp))
                self.assertEqual(flagged_ids(outcome), expected, outcome.stderr or outcome.stdout)
                self.assertEqual(outcome.exit_code, 2 if "G5.R2" in expected else 0)

    def test_babysit_remedy_points_at_the_playbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_routing(ROUTING_MUTATIONS[2][2], Path(tmp))
        self.assertIn("playbooks/babysit.md", outcome.stderr)

    def test_a_fan_out_skill_licenses_parallel_agents(self):
        for skill in ("pstack:swarm", "pstack:arena", "architect", "pstack:interrogate"):
            with self.subTest(skill), tempfile.TemporaryDirectory() as tmp:
                outcome = run_routing(rplus(THIRD, ("fan_out", lambda t, s=skill: t.skill(s, at(1, 30)))), Path(tmp))
                self.assertEqual((outcome.exit_code, outcome.stdout), (0, ""))

    def test_a_fan_out_skill_run_by_the_acting_subagent_licenses_its_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Transcript().slash("pstack:poteto-mode", at(0), "build it").write(Path(tmp) / "session.jsonl")
            sub = Transcript().skill("pstack:swarm", at(1))
            spawn(sub, at(2), "msg_2")
            spawn(sub, at(2, 30), "msg_2")
            sub.tool("Agent", AGENT_INPUT, at(3), None, tool_id=AGENT_ID)
            sub.records[-1]["message"]["id"] = "msg_2"
            sub.write(Path(tmp) / "session" / "subagents" / "agent-d1.jsonl")
            raw = json.loads(routing_payload(root, "Agent", AGENT_INPUT, AGENT_ID))
            raw.update(agent_id="d1", agent_type="general-purpose")
            outcome = hook.run(json.dumps(raw), env(forbidden_runner, Mode.BLOCK))
        self.assertEqual((outcome.exit_code, outcome.stdout), (0, ""))

    def test_agents_in_an_earlier_message_are_not_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_routing(rwithout(ROUTING_GREEN, "sibling"), Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout), (0, ""))

    def test_a_session_without_poteto_is_never_parsed(self):
        for case in (rwithout(THIRD, "poteto"), replace(rwithout(ROUTING_GREEN, "poteto"), tool="Skill", inp={"skill": "babysit"})):
            with self.subTest(case.tool), tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(evidence, "load_session", side_effect=AssertionError("parsed")):
                outcome = run_routing(case, Path(tmp))
                self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_warn_mode_lets_babysit_run_with_the_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_routing(ROUTING_MUTATIONS[2][2], Path(tmp), Mode.WARN)
        self.assertEqual(outcome.exit_code, 0)
        self.assertIn("FAIL G5.R2", said(outcome))


if __name__ == "__main__":
    unittest.main()

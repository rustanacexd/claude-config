import json
import tempfile
import unittest
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, Tuple
from unittest import mock

from support import WORKTREE, Piece, Transcript, at, env, flagged_ids, forbidden_runner, said
import evidence
import hook
from core import Mode

PLAYBOOK_STEPS = "# Feature\n\n1. `how` over the affected subsystem.\n2. **Delegate** the code to a subagent with its own worktree.\n   1. nested, not a step\n"
POTETO_INDEX = "## Principles\n\n- **Prove It Works** (**principle-prove-it-works**). After a task.\n- **Model the Domain** (**principle-model-the-domain**). Stateful logic.\n"
REPLY = "Done. **Prove It Works** shaped the check: the suite ran on the final code."
SRC = f"{WORKTREE}/src/a.py"


def files(tmp: Path) -> Tuple[str, str, str]:
    playbook = tmp / "skills/poteto-mode/playbooks/feature.md"
    skill = tmp / "skills/poteto-mode/SKILL.md"
    principle = tmp / "skills/principle-prove-it-works/SKILL.md"
    for path, text in ((playbook, PLAYBOOK_STEPS), (skill, POTETO_INDEX), (principle, "# Prove it works\n")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return str(playbook), str(skill), str(principle)


@dataclass(frozen=True)
class StopCase:
    pieces: Tuple[Tuple[str, Piece], ...]
    reply: str = REPLY
    stop_hook_active: bool = False
    agent_id: Optional[str] = None
    sub_pieces: Tuple[Tuple[str, Piece], ...] = ()


def green(tmp: Path) -> StopCase:
    playbook, skill, principle = files(tmp)
    return StopCase(pieces=(
        ("poteto", lambda t: t.slash("pstack:poteto-mode", at(0), "add the feature")),
        ("skill_md", lambda t: t.read(skill, at(0, 30))),
        ("playbook", lambda t: t.read(playbook, at(1))),
        ("task1", lambda t: t.task("1. `how` over the affected subsystem.", at(2))),
        ("task2", lambda t: t.task("2. Delegate the code to a subagent with its own worktree.", at(2, 10))),
        ("principle", lambda t: t.read(principle, at(3))),
        ("edit", lambda t: t.edit(SRC, at(4))),
        ("up", lambda t: t.bash("npm run --silent e2e:control -- up", at(4, 30))),
        ("test", lambda t: t.bash("python3 -m unittest discover -s tests", at(5))),
        ("down", lambda t: t.bash("npm run --silent e2e:control -- down", at(5, 30))),
        ("advisor", lambda t: t.advisor(at(6))),
    ))


def stop_payload(path: Path, case: StopCase) -> str:
    d = {"session_id": "sess-1", "transcript_path": str(path), "cwd": "/work", "hook_event_name": "Stop",
         "stop_hook_active": case.stop_hook_active, "last_assistant_message": case.reply}
    if case.agent_id:
        d["agent_id"] = case.agent_id
    return json.dumps(d)


def run_stop(case: StopCase, tmp: Path, mode: Mode = Mode.BLOCK, e=None):
    t = Transcript()
    for _, piece in sorted(case.pieces, key=lambda p: _when(p[1])):
        piece(t)
    t.say(case.reply, at(7))
    path = t.write(tmp / "session.jsonl")
    if case.sub_pieces:
        sub = Transcript()
        for _, piece in case.sub_pieces:
            piece(sub)
        sub.write(tmp / "session" / "subagents" / "agent-d1.jsonl")
    return hook.run(stop_payload(path, case), e or env(forbidden_runner, mode))


def _when(piece: Piece) -> str:
    probe = Transcript()
    piece(probe)
    return probe.records[0]["timestamp"]


def without(case, *names):
    return replace(case, pieces=tuple(p for p in case.pieces if p[0] not in names))


def plus(case, *pieces):
    return replace(case, pieces=case.pieces + pieces)


def G3(*ns):
    return frozenset(f"G3.R{n}" for n in ns)


def mutations(tmp: Path):
    g = green(tmp)
    _, _, principle = files(tmp)
    return (
        ("no task after poteto-mode ran", G3(1),
         plus(without(g, "task1", "task2", "poteto"),
              ("early", lambda t: t.task("1. `how` over the affected subsystem.", at(0))),
              ("early2", lambda t: t.task("2. Delegate the code to a subagent with its own worktree.", at(0, 1))),
              ("poteto", lambda t: t.slash("pstack:poteto-mode", at(0, 2), "add the feature")))),
        ("a playbook step left out of the todolist", G3(2), without(g, "task2")),
        ("a cited principle never read", G3(3), without(g, "principle")),
        ("a cited principle read only in part", G3(3),
         plus(without(g, "principle"), ("partial", lambda t: t.read(principle, at(3), limit=5)))),
        ("a principle cited by its slug", G3(3),
         replace(without(g, "principle"), reply="Done. principle-model-the-domain decided the shape.")),
        ("no advisor call", G3(4), without(g, "advisor")),
        ("advisor before the last edit", G3(4),
         plus(without(g, "advisor"), ("early", lambda t: t.advisor(at(3, 30))))),
        ("a push after the advisor", G3(4), plus(g, ("push", lambda t: t.bash("git push origin feat", at(6, 30))))),
        ("a delegate's edit after the advisor", G3(4),
         replace(g, sub_pieces=(("sub_edit", lambda t: t.edit(f"{WORKTREE}/src/b.py", at(6, 30))),
                                ("sub_test", lambda t: t.bash("python3 -m unittest", at(6, 40)))))),
        ("done claimed with an edit after the last test", G3(5),
         plus(without(g, "test"), ("test", lambda t: t.bash("python3 -m unittest discover -s tests", at(3, 50))))),
        ("done claimed with no test this turn", G3(5), without(g, "test")),
        ("an app session left up", G3(6), without(g, "down")),
    )


class StopMutationMatrix(unittest.TestCase):
    def test_green_allows_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_stop(green(Path(tmp)), Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_each_mutation_flags_exactly_its_requirement(self):
        with tempfile.TemporaryDirectory() as names_tmp:
            names = [m[0] for m in mutations(Path(names_tmp))]
        for i, name in enumerate(names):
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                _, expected, case = mutations(Path(tmp))[i]
                outcome = run_stop(case, Path(tmp))
                self.assertEqual(flagged_ids(outcome), expected, outcome.stderr or outcome.stdout)
                blocking = expected & G3(1, 3, 4)
                self.assertEqual(outcome.exit_code, 2 if blocking else 0)


class StopScope(unittest.TestCase):
    def outcome(self, change, mode=Mode.BLOCK):
        with tempfile.TemporaryDirectory() as tmp:
            return run_stop(change(green(Path(tmp)), Path(tmp)), Path(tmp), mode)

    def test_a_second_stop_in_the_same_turn_never_blocks(self):
        outcome = self.outcome(lambda g, tmp: replace(without(g, "advisor"), stop_hook_active=True))
        self.assertEqual((outcome.exit_code, outcome.stderr), (0, ""))
        message = json.loads(outcome.stdout)["systemMessage"]
        self.assertIn("already continuing this turn because a Stop hook blocked it once", message)
        self.assertIn("FAIL G3.R4", message)

    def test_warn_mode_reports_through_system_message(self):
        outcome = self.outcome(lambda g, tmp: without(g, "advisor"), Mode.WARN)
        self.assertEqual(outcome.exit_code, 0)
        self.assertIn("FAIL G3.R4", json.loads(outcome.stdout)["systemMessage"])

    def test_r4_and_r5_look_only_at_the_current_turn(self):
        def next_turn(g, tmp):
            return replace(plus(without(g, "advisor", "test"), ("ask", lambda t: t.user("thanks, what changed?", at(6, 30)))),
                           reply="I changed src/a.py, and it is done.")
        self.assertEqual(said(self.outcome(next_turn)), "")

    def test_a_negated_done_claim_is_not_a_claim(self):
        outcome = self.outcome(lambda g, tmp: replace(without(g, "test"), reply="This is not done yet; tests still need to run."))
        self.assertEqual((outcome.exit_code, outcome.stdout), (0, ""))

    def test_a_todo_file_counts_as_the_todolist(self):
        def todo_file(g, tmp):
            steps = "- [ ] 1. `how` over the affected subsystem.\n- [ ] 2. Delegate the code to a subagent with its own worktree.\n"
            return plus(without(g, "task1", "task2"),
                        ("todo", lambda t: t.tool("Write", {"file_path": "/tmp/run/todo.md", "content": steps}, at(2), "ok")))
        outcome = self.outcome(todo_file)
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_a_todo_file_written_from_bash_counts_and_its_skip_lines_are_read_from_disk(self):
        def bash_todo(g, tmp):
            todo = tmp / "todo.md"
            todo.write_text("- [ ] 1. `how` over the affected subsystem.\n- [ ] 2. Delegate the code to a subagent with "
                            "its own worktree.\n- skip: G3.R4 the advisor tool is offline\n")
            return plus(without(g, "task1", "task2", "advisor"),
                        ("todo", lambda t: t.bash(f"cat > {todo} <<'EOF'\n- [ ] 1. how\nEOF", at(2))))
        outcome = self.outcome(bash_todo)
        self.assertEqual(outcome.exit_code, 0, outcome.stderr)
        self.assertIn("G3.R4 skipped: the advisor tool is offline", said(outcome))
        self.assertNotIn("G3.R2", said(outcome))

    def test_the_log_records_the_mode_of_each_failed_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "gates.jsonl"
            installed = replace(env(forbidden_runner, Mode.WARN), gate_modes={"G3_R1": Mode.BLOCK}, log_path=log)
            outcome = run_stop(without(green(Path(tmp)), "task1", "task2", "advisor"), Path(tmp), e=installed)
            passing = run_stop(green(Path(tmp)), Path(tmp), e=installed)
            failed_row, passing_row = map(json.loads, log.read_text().splitlines())
        self.assertEqual((outcome.exit_code, passing.exit_code), (2, 0))
        self.assertEqual(failed_row["modes"], {"G3.R1": "block", "G3.R4": "warn"})
        self.assertEqual((passing_row["failed"], "modes" in passing_row), ([], False))

    def test_a_skip_line_naming_the_step_number_covers_it(self):
        outcome = self.outcome(lambda g, tmp: plus(without(g, "task2"), ("skip", lambda t: t.task("2. skip: one file, no delegate", at(2, 10)))))
        self.assertEqual((outcome.exit_code, outcome.stdout), (0, ""))

    def test_r2_keeps_playbooks_read_before_poteto_mode_was_run_again(self):
        def rerun(g, tmp):
            return plus(without(g, "task2"), ("again", lambda t: t.slash("pstack:poteto-mode", at(3, 30), "and the tests")),
                        ("task3", lambda t: t.task("3. add the tests", at(3, 40))))
        self.assertEqual(flagged_ids(self.outcome(rerun)), G3(2))

    def test_a_principle_skill_run_counts_as_a_read(self):
        outcome = self.outcome(lambda g, tmp: plus(without(g, "principle"),
                                                   ("skill", lambda t: t.skill("pstack:principle-prove-it-works", at(3)))))
        self.assertEqual((outcome.exit_code, outcome.stdout), (0, ""))

    def test_a_declared_skip_resolves_r4(self):
        outcome = self.outcome(lambda g, tmp: plus(without(g, "advisor"),
                                                   ("skip", lambda t: t.task("skip: G3.R4 the advisor tool is offline", at(5, 40)))))
        self.assertEqual(outcome.exit_code, 0)
        self.assertIn("G3.R4 skipped: the advisor tool is offline", said(outcome))

    def test_a_subagent_stop_is_not_gated(self):
        def as_subagent(g, tmp):
            Transcript().slash("pstack:poteto-mode", at(0)).write(tmp / "session" / "subagents" / "agent-d1.jsonl")
            return replace(without(g, "advisor", "principle"), agent_id="d1")
        outcome = self.outcome(as_subagent)
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_a_session_without_poteto_is_never_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Transcript().user("fix it", at(0))
            t.edit(SRC, at(1))
            path = t.write(Path(tmp) / "s.jsonl")
            with mock.patch.object(evidence, "load_session", side_effect=AssertionError("parsed")):
                outcome = hook.run(stop_payload(path, StopCase(pieces=())), env(forbidden_runner))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_an_unreadable_transcript_allows(self):
        outcome = hook.run(stop_payload(Path("/nonexistent/s.jsonl"), StopCase(pieces=())), env(forbidden_runner))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()

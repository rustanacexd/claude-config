import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from support import (
    OPEN_ID, PR_CREATE, WORKTREE, FakeGit, PrCase, Transcript, at, env, flagged_ids, payload, plus, run_pr_case, said, without,
)
import evidence
import hook
from core import Mode

GREEN = PrCase()


def run(case):
    with tempfile.TemporaryDirectory() as tmp:
        return run_pr_case(case, Path(tmp))


class PrGate(unittest.TestCase):
    def test_a_commit_a_scratch_file_or_a_todo_tick_after_deslop_does_not_reset_it(self):
        case = plus(GREEN, ("commit", lambda t: t.bash("git commit -am 'fix: a thing'", at(6))),
                    ("body", lambda t: t.tool("Write", {"file_path": "/tmp/body.md", "content": "## Why"}, at(6, 30))),
                    ("todo", lambda t: t.tool("Write", {"file_path": f"{WORKTREE}/todo.md", "content": "- [x] deslop"}, at(6, 40))))
        self.assertEqual(run(case).exit_code, 0)

    def test_no_edits_passes_and_says_so(self):
        outcome = run(without(GREEN, "edit", "deslop", "no_comments"))
        self.assertEqual((outcome.exit_code, outcome.stdout), (0, ""))

    def test_a_delegated_edit_needs_a_later_deslop_and_a_delegated_deslop_counts(self):
        def run_with_agent(sub_pieces):
            with tempfile.TemporaryDirectory() as tmp:
                root = Transcript()
                for _, piece in GREEN.pieces:
                    piece(root)
                root.bash(PR_CREATE, at(7), None, tool_id=OPEN_ID)
                path = root.write(Path(tmp) / "sess.jsonl")
                sub = Transcript()
                for piece in sub_pieces:
                    piece(sub)
                sub.write(Path(tmp) / "sess" / "subagents" / "agent-a9.jsonl")
                return hook.run(payload(path, PR_CREATE, tool_use_id=OPEN_ID), env(FakeGit()))

        late_edit = lambda t: t.edit(f"{WORKTREE}/src/c.py", at(6))
        self.assertEqual(flagged_ids(run_with_agent([late_edit])), frozenset({"G2.R1", "G2.R2"}))
        cleaned = [late_edit, lambda t: t.skill("pstack:deslop", at(6, 10)), lambda t: t.skill("no-comments", at(6, 20))]
        self.assertEqual(run_with_agent(cleaned).exit_code, 0)

    def test_r1_to_r3_hold_only_in_poteto_sessions_and_r4_everywhere(self):
        bare = without(GREEN, "poteto", "deslop", "no_comments", "technical_writing", "unslop")
        self.assertEqual(flagged_ids(run(replace(bare, git=FakeGit(files=("a.py",))))), frozenset())
        self.assertEqual(flagged_ids(run(replace(bare, command="git commit -n -m x"))), frozenset({"G2.R4"}))

    def test_a_declared_skip_allows_no_verify_and_is_echoed(self):
        case = plus(replace(GREEN, command="git commit --no-verify -m x"),
                    ("skip", lambda t: t.task("skip: G2.R4 the hook needs a network the sandbox lacks", at(6))))
        outcome = run(case)
        self.assertEqual(outcome.exit_code, 0, outcome.stderr)
        self.assertIn("G2.R4 skipped: the hook needs a network the sandbox lacks", said(outcome))


class MandateGate(unittest.TestCase):
    def test_a_one_file_diff_needs_no_mandate(self):
        outcome = run(replace(without(GREEN, "poteto"), git=FakeGit(files=("README.md",))))
        self.assertEqual((outcome.exit_code, outcome.stdout), (0, ""))

    def test_the_base_flag_and_head_flag_pick_the_diff(self):
        git = FakeGit()
        run(replace(without(GREEN, "poteto"), git=git, command="gh pr create -B release -H me:topic --title t --body b"))
        self.assertEqual(git.calls, [["git", "diff", "--name-only", "origin/release...topic"]])
        git = FakeGit()
        run(replace(without(GREEN, "poteto"), git=git, command="gh stack submit --auto"))
        self.assertEqual(git.calls[-1], ["git", "diff", "--name-only", "origin/main...HEAD"])

    def test_a_passing_open_outside_poteto_never_parses_the_transcript(self):
        parses = []
        original = evidence.load_session
        evidence.load_session = lambda *a: parses.append(a) or original(*a)
        try:
            outcome = run(replace(without(GREEN, "poteto"), git=FakeGit(files=("README.md",))))
        finally:
            evidence.load_session = original
        self.assertEqual((outcome.exit_code, outcome.stdout, parses), (0, "", []))

    def test_a_poteto_session_skips_git(self):
        git = FakeGit(down="git must not run")
        self.assertEqual(run(replace(GREEN, git=git)).exit_code, 0)
        self.assertEqual(git.calls, [])

    def test_asking_for_help_opens_no_pr(self):
        for command in ("gh pr create --help", "gh stack submit -h", "gh pr create --fill -h"):
            for case in (without(GREEN, "deslop", "no_comments"), without(GREEN, "poteto")):
                with self.subTest(command=command, pieces=[name for name, _ in case.pieces]):
                    outcome = run(replace(case, command=command))
                    self.assertEqual((outcome.exit_code, outcome.stderr), (0, ""))

    def test_warn_on_one_gate_still_lets_another_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = without(GREEN, "poteto")
            outcome = run_pr_case(case, Path(tmp), gate_modes={"G6": Mode.WARN})
        self.assertEqual(outcome.exit_code, 0)
        self.assertIn("FAIL G6.R1", said(outcome))

    def test_a_subagent_counts_the_roots_poteto_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Transcript().slash("pstack:poteto-mode", at(0))
            path = root.write(Path(tmp) / "sess.jsonl")
            sub = Transcript()
            sub.bash(PR_CREATE, at(7), None, tool_id=OPEN_ID)
            sub.write(Path(tmp) / "sess" / "subagents" / "agent-a3.jsonl")
            outcome = hook.run(payload(path, PR_CREATE, tool_use_id=OPEN_ID, agent_id="a3"), env(FakeGit()))
        self.assertEqual(outcome.exit_code, 0, outcome.stderr)


if __name__ == "__main__":
    unittest.main()

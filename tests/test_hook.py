import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from support import (
    GREEN_FACTS, GREEN_PIECES, HEAD, MERGE_ID, PR, Case, FakeGh, Transcript, at, env, failed_ids, forbidden_runner,
    gh_at, inline, merge_command, payload, plus, run_case, without,
)
import hook
import g1_merge
from core import Mode

GREEN = Case()


def context(outcome):
    return json.loads(outcome.stdout)["hookSpecificOutput"]["additionalContext"]


class FastPath(unittest.TestCase):
    def test_commands_without_a_merge_never_reach_gh_or_the_transcript(self):
        missing = Path("/nonexistent/session.jsonl")
        for command in ("ls -la", "git merge main", 'echo "gh pr merge 5"', "grep -c 'gh pr merge' log.txt", "gh pr merge --help",
                        "cat > t.md <<EOF\ngh pr merge 5\nEOF"):
            with self.subTest(command):
                outcome = hook.run(payload(missing, command), env(forbidden_runner))
                self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))


class Requirements(unittest.TestCase):
    def run_case(self, case, mode=Mode.BLOCK):
        with tempfile.TemporaryDirectory() as tmp:
            return run_case(case, Path(tmp), mode)[0]

    def test_r3_is_per_surface_on_changed_at(self):
        facts = replace(GREEN_FACTS, inline=(inline(3000000001, gh_at(5, 30), "P1: this drops a row"),))
        self.assertEqual(failed_ids(self.run_case(replace(GREEN, facts=facts))), frozenset({"G1.R3"}))
        read_inline = ("inline", lambda t: t.bash(f"gh api repos/example/repo/pulls/{PR}/comments", at(6, 10), "[...]"))
        self.assertEqual(self.run_case(plus(replace(GREEN, facts=facts), read_inline)).exit_code, 0)

    def test_r6_needs_an_unnegated_landing_verb_from_the_user(self):
        def said(text):
            return plus(without(GREEN, "user"), ("user", lambda t: t.user(text, at(0))))

        self.assertEqual(failed_ids(self.run_case(said("please don't land this yet"))), frozenset({"G1.R6"}))
        self.assertEqual(self.run_case(said("<https://github.com/example/repo/pull/42> merge it")).exit_code, 0)

    def test_r6_ignores_land_authorized_lines(self):
        for text in ("please don't land this yet", "go ahead with 42"):
            with self.subTest(text):
                case = plus(without(GREEN, "user"), ("user", lambda t, text=text: t.user(text, at(0))),
                            ("quote", lambda t, text=text: t.task(f'land authorized: "{text}"', at(0, 30))))
                self.assertEqual(failed_ids(self.run_case(case)), frozenset({"G1.R6"}))

    def test_a_post_without_an_id_claims_only_comments_made_while_it_ran(self):
        quiet_post = ("post", lambda t: t.bash(f"gh pr comment {PR} --body-file /tmp/n.md >/dev/null", at(3, 50), ""))
        self.assertEqual(self.run_case(plus(GREEN, quiet_post)).exit_code, 0)

    def test_gh_unavailable_still_reports_transcript_requirements(self):
        case = without(replace(GREEN, facts=replace(GREEN_FACTS, down="gh: not logged in")), "advisor", "playbook")
        outcome = self.run_case(case)
        self.assertEqual(failed_ids(outcome), frozenset({"G1.R1", "G1.R2", "G1.R3", "G1.R4", "G1.R5"}))
        self.assertIn("ok   G1.R6", outcome.stderr)
        self.assertIn("gh auth status", outcome.stderr)

    def test_dynamic_selector_never_asks_gh(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Transcript()
            for _, piece in GREEN_PIECES:
                piece(t)
            command = f"for p in 41 42; do gh pr merge $p --squash --match-head-commit {HEAD}; done"
            t.bash(command, at(7), None, tool_id=MERGE_ID)
            outcome = hook.run(payload(t.write(Path(tmp) / "s.jsonl"), command), env(forbidden_runner))
        self.assertEqual(failed_ids(outcome), frozenset({"G1.R1", "G1.R2", "G1.R3"}))
        self.assertIn("shell expression ($p)", outcome.stderr)

    def test_warn_mode_allows_and_says_what_would_have_blocked(self):
        outcome = self.run_case(without(GREEN, "advisor"), Mode.WARN)
        self.assertEqual((outcome.exit_code, outcome.stderr), (0, ""))
        self.assertIn("NOT blocked", context(outcome))
        self.assertIn("FAIL G1.R4", context(outcome))


class Subagent(unittest.TestCase):
    def run_as_subagent(self, root_pieces, sub_pieces):
        with tempfile.TemporaryDirectory() as tmp:
            root, sub = Transcript(), Transcript()
            for piece in root_pieces:
                piece(root)
            for piece in sub_pieces:
                piece(sub)
            sub.bash(merge_command(), at(7), None, tool_id=MERGE_ID)
            root_path = root.write(Path(tmp) / "sess.jsonl")
            sub.write(Path(tmp) / "sess" / "subagents" / "agent-a1.jsonl")
            return hook.run(payload(root_path, merge_command(), agent_id="a1"), env(FakeGh(GREEN_FACTS)))

    def test_evidence_must_be_in_the_acting_agents_file(self):
        user = lambda t: t.user("land PR 42", at(0))
        push = lambda t: t.bash("git push", at(2))
        playbook = lambda t: t.read("/p/playbooks/shipping.md", at(1))
        advisor = lambda t: t.advisor(at(5))
        read = lambda t: t.bash(f"gh pr view {PR} --comments", at(6), "...")
        self.assertEqual(self.run_as_subagent([user, push], [playbook, advisor, read]).exit_code, 0)
        outcome = self.run_as_subagent([user, push, advisor], [playbook, read])
        self.assertEqual(failed_ids(outcome), frozenset({"G1.R4"}))


class Crash(unittest.TestCase):
    def test_a_gate_bug_exits_2(self):
        original = g1_merge.MergeGate.subjects
        g1_merge.MergeGate.subjects = lambda self, h: 1 / 0
        try:
            stderr = io.StringIO()
            code = hook.main(io.StringIO(payload(Path("/x.jsonl"), merge_command())), io.StringIO(), stderr, {})
        finally:
            g1_merge.MergeGate.subjects = original
        self.assertEqual(code, 2)
        self.assertIn("crashed (ZeroDivisionError", stderr.getvalue())

    def test_log_records_the_python_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "g.jsonl"
            t = Transcript()
            t.bash(merge_command(), at(7), None, tool_id=MERGE_ID)
            e = replace(env(FakeGh(GREEN_FACTS)), log_path=log)
            hook.run(payload(t.write(Path(tmp) / "s.jsonl"), merge_command()), e)
            row = json.loads(log.read_text())
        self.assertIn("python", row)
        self.assertIn("G1.R4", row["failed"])


if __name__ == "__main__":
    unittest.main()

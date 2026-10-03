import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from support import (
    BOT_ID, GREEN_FACTS, HEAD, OTHER, PASS_BODY, PASS_ID, PR, WORKTREE, Case, FakeGit, PrCase, at, comment, flagged_ids, gh_at,
    merge_command, plus, review, run_case, run_pr_case, failed_ids, without,
)

GREEN = Case()


def R(*ns):
    return frozenset(f"G1.R{n}" for n in ns)


MUTATIONS = (
    ("no advisor call", R(4), without(GREEN, "advisor")),
    ("advisor before the last push", R(4), plus(without(GREEN, "advisor"), ("early", lambda t: t.advisor(at(1, 30))))),
    ("comments never read", R(3), without(GREEN, "read_comments")),
    ("read started before the PASS landed", R(3),
     plus(without(GREEN, "read_comments"), ("stale", lambda t: t.bash(f"gh pr view {PR} --comments", at(3, 45), "...")))),
    ("a comment edited after the read", R(3),
     replace(GREEN, facts=replace(GREEN_FACTS, issue=(
         comment(BOT_ID, gh_at(3), "Codex review: found a P1", user="bot[bot]", updated=gh_at(6, 30)),
         GREEN_FACTS.issue[1])))),
    ("comments read inside the merge command", R(3),
     replace(without(GREEN, "read_comments"), command=f"gh pr view {PR} --comments && {merge_command()}")),
    ("the read failed", R(3),
     plus(without(GREEN, "read_comments"), ("err", lambda t: t.bash(f"gh pr view {PR} --comments", at(6), "denied", is_error=True)))),
    ("head moved after the verdict", R(1, 2), replace(GREEN, facts=replace(GREEN_FACTS, head=OTHER))),
    ("the only PASS on head was posted by this session, matched by id", R(1),
     plus(GREEN, ("self_post", lambda t: t.bash(f"gh pr comment {PR} --body-file /tmp/v.md", at(5, 30),
                                                 f"https://github.com/example/repo/pull/{PR}#issuecomment-{PASS_ID}")))),
    ("the PASS was posted with output discarded", R(1),
     plus(GREEN, ("self_post", lambda t: t.bash(f"gh pr comment {PR} --body-file /tmp/v.md >/dev/null 2>&1", at(4, 1), "")))),
    ("the PASS was posted with gh api --silent", R(1),
     plus(GREEN, ("self_post", lambda t: t.bash(
         f"gh api repos/example/repo/issues/{PR}/comments -f body=@/tmp/v.md --silent", at(4, 1), "")))),
    ("the PASS was posted as a review body", R(1),
     plus(replace(GREEN, facts=replace(GREEN_FACTS, issue=GREEN_FACTS.issue[:1],
                                       reviews=GREEN_FACTS.reviews + (review(2000000002, gh_at(4), PASS_BODY),))),
          ("self_post", lambda t: t.bash(f"gh pr review {PR} --comment --body-file /tmp/v.md", at(4, 1),
                                         f"- Reviewed pull request #{PR}")))),
    ("a later FAIL on the head", R(1),
     replace(GREEN, facts=replace(GREEN_FACTS, issue=GREEN_FACTS.issue + (comment(1000000003, gh_at(4, 30), f"FAIL on {HEAD[:8]}"),)))),
    ("no pin", R(2), replace(GREEN, command=f"gh pr merge {PR} --repo example/repo --squash")),
    ("pin is a shell variable", R(2), replace(GREEN, command=merge_command("$H"))),
    ("pin is a 12-character prefix", R(2), replace(GREEN, command=merge_command(HEAD[:12]))),
    ("compaction after the playbook read", R(5), plus(GREEN, ("compact", lambda t: t.compact(at(1, 30))))),
    ("/compact after the playbook read", R(5), plus(GREEN, ("compact", lambda t: t.local_compact(at(1, 30))))),
    ("playbook read through head", R(5),
     plus(without(GREEN, "playbook"), ("partial", lambda t: t.bash("cat /p/playbooks/shipping.md | head -60", at(1), "# Shipping")))),
    ("no user authorization", R(6),
     plus(without(GREEN, "user"), ("user", lambda t: t.user("how is PR 42 doing?", at(0))))),
    ("gh unreachable", R(1, 2, 3), replace(GREEN, facts=replace(GREEN_FACTS, down="network down"))),
    ("transcript unreadable", R(1, 3, 4, 5, 6), replace(GREEN, delete_transcript=True)),
    ("skip G1.R6 is not honoured", R(6),
     plus(without(GREEN, "user"), ("user", lambda t: t.user("how is PR 42 doing?", at(0))),
          ("skip", lambda t: t.task("skip: G1.R6 the user said go", at(5, 30))))),
)


class MutationMatrix(unittest.TestCase):
    def test_green_allows_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome, gh = run_case(GREEN, Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))
        self.assertTrue(gh.calls, "GREEN must consult GitHub")

    def test_each_mutation_fails_exactly_its_requirement(self):
        for name, expected, case in MUTATIONS:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                outcome, _ = run_case(case, Path(tmp))
                self.assertEqual(outcome.exit_code, 2, outcome.stdout)
                self.assertEqual(failed_ids(outcome), expected, outcome.stderr)

    def test_declared_skip_resolves_r4_and_is_echoed(self):
        case = plus(without(GREEN, "advisor"), ("skip", lambda t: t.task("skip: G1.R4 advisor offline, user told", at(5, 30))))
        with tempfile.TemporaryDirectory() as tmp:
            outcome, _ = run_case(case, Path(tmp))
        self.assertEqual(outcome.exit_code, 0, outcome.stderr)
        context = json.loads(outcome.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("G1.R4 skipped: advisor offline, user told", context)


PR_GREEN = PrCase()


def ids(*rids):
    return frozenset(rids)


PR_MUTATIONS = (
    ("no deslop", ids("G2.R1"), without(PR_GREEN, "deslop")),
    ("an edit after deslop", ids("G2.R1"), plus(PR_GREEN, ("late", lambda t: t.edit(f"{WORKTREE}/src/b.py", at(2, 30))))),
    ("no no-comments", ids("G2.R2"), without(PR_GREEN, "no_comments")),
    ("no-comments before the last edit", ids("G2.R2"),
     plus(without(PR_GREEN, "no_comments"), ("early", lambda t: t.skill("pstack:no-comments", at(0, 30))))),
    ("no technical-writing", ids("G2.R3"), without(PR_GREEN, "technical_writing")),
    ("unslop read only in part", ids("G2.R3"),
     plus(without(PR_GREEN, "unslop"), ("partial", lambda t: t.read("/p/skills/unslop/SKILL.md", at(5), limit=40)))),
    ("git commit --no-verify", ids("G2.R4"), replace(PR_GREEN, command="git commit --no-verify -m 'fix: a thing'")),
    ("git commit -an", ids("G2.R4"), replace(PR_GREEN, command="git commit -an -m 'fix: a thing'")),
    ("git -C dir push --no-verify", ids("G2.R4"), replace(PR_GREEN, command="git -C /work push --no-verify origin fix")),
    ("multi-file PR without poteto-mode", ids("G6.R1"), without(PR_GREEN, "poteto")),
    ("git cannot report the diff", ids("G6.R1"), replace(without(PR_GREEN, "poteto"), git=FakeGit(down="not a git repository"))),
)


class PrMutationMatrix(unittest.TestCase):
    def test_green_allows_silently(self):
        for command in (PR_GREEN.command, "git commit -m 'fix: a thing' && git push origin fix", "gh stack submit --auto"):
            with self.subTest(command), tempfile.TemporaryDirectory() as tmp:
                outcome = run_pr_case(replace(PR_GREEN, command=command), Path(tmp))
                self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_each_mutation_flags_exactly_its_requirement(self):
        for name, expected, case in PR_MUTATIONS:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                outcome = run_pr_case(case, Path(tmp))
                self.assertEqual(flagged_ids(outcome), expected, outcome.stderr or outcome.stdout)
                self.assertEqual(outcome.exit_code, 0 if expected == ids("G2.R3") else 2)


if __name__ == "__main__":
    unittest.main()

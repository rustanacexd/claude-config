import unittest
from pathlib import Path

import support  # noqa: F401
from evidence import parse_shell


def calls(command, start="/start"):
    return [(i.tool, i.sub) for i in parse_shell(command, Path(start))]


def merges(command):
    return [i for i in parse_shell(command, Path("/start")) if i.tool == "gh" and i.sub == ("pr", "merge")]


class ParseShell(unittest.TestCase):
    def test_chained_commands_each_yield_an_invocation(self):
        self.assertEqual(
            calls("gh pr view 1 --comments && gh pr merge 1; git push || echo x"),
            [("gh", ("pr", "view")), ("gh", ("pr", "merge")), ("git", ("push",)), ("echo", ())],
        )

    def test_heredoc_body_is_data(self):
        self.assertEqual(merges("python3 - <<'PY'\nimport re\nre.search('gh pr merge 5', s)\nPY\necho ok"), [])
        self.assertEqual(merges("cat > /tmp/body.md <<EOF\nthen run gh pr merge 5\nEOF"), [])

    def test_heredoc_fed_to_a_shell_is_a_script(self):
        self.assertEqual(len(merges("bash <<'SH'\ngh pr merge 5 --squash\nSH")), 1)

    def test_quoted_mentions_are_not_commands(self):
        self.assertEqual(merges("grep -c 'gh pr merge' <<<\"$t\""), [])
        self.assertEqual(merges('echo "next: gh pr merge 5"'), [])

    def test_command_substitution_runs_and_hides_heredoc_text(self):
        cmd = "gh pr comment 1 --body \"$(cat <<'EOF'\nit's done (gh pr merge 9 later\nEOF\n)\""
        self.assertEqual(calls(cmd), [("cat", ()), ("gh", ("pr", "comment"))])
        self.assertEqual(calls("x=$(gh pr view 5 --json headRefOid)"), [("gh", ("pr", "view"))])

    def test_dynamic_words(self):
        (m,) = merges('gh pr merge "$p" --match-head-commit $H --repo example/repo')
        self.assertEqual([(w.text, w.dynamic) for w in m.words],
                         [("$p", True), ("--match-head-commit", False), ("$H", True), ("--repo", False), ("example/repo", False)])
        (m,) = merges("gh pr merge 3 --match-head-commit $(git rev-parse HEAD)")
        self.assertTrue(m.value_of("--match-head-commit").dynamic)

    def test_cd_sets_the_workdir_of_later_commands(self):
        invs = parse_shell("cd /repo && gh pr merge 3; cd sub && git push; cd $X && git push", Path("/start"))
        self.assertEqual([i.workdir for i in invs], [Path("/repo"), Path("/repo/sub"), None])

    def test_pipe_into_head(self):
        cat, head = parse_shell("cat /p/playbooks/shipping.md | head -60", Path("/s"))
        self.assertEqual((cat.tool, cat.pipes_into, head.pipes_into), ("cat", ("head",), ()))

    def test_loop_bodies_and_wrappers(self):
        self.assertEqual(len(merges("for p in 1 2; do gh pr merge $p --squash; done")), 1)
        self.assertEqual(len(merges("GH_DEBUG=1 env FOO=bar command gh pr merge 3")), 1)
        self.assertEqual(len(merges("bash -c 'gh pr merge 9'")), 1)

    def test_a_script_flag_inside_a_shell_flag_cluster(self):
        for command in ('bash -lc "gh pr merge 9"', "sh -ec 'gh pr merge 9'", "bash -e -c 'gh pr merge 9'",
                        "dash -xc 'gh pr merge 9'", "ksh -c 'gh pr merge 9'"):
            with self.subTest(command):
                self.assertEqual(len(merges(command)), 1)
        self.assertEqual(merges("bash -l script.sh"), [])

    def test_wrappers_skip_their_own_flags_and_arguments(self):
        for command in ("timeout 30 gh pr merge 1", "timeout -k 5 --foreground 30s gh pr merge 1",
                        "caffeinate -i gh pr merge 1", "caffeinate -t 600 gh pr merge 1", "stdbuf -oL gh pr merge 1",
                        "stdbuf -o L gh pr merge 1", "nice -n 5 gh pr merge 1", "nohup gh pr merge 1"):
            with self.subTest(command):
                (m,) = merges(command)
                self.assertEqual([w.text for w in m.words], ["1"])

    def test_fd_redirects_are_not_arguments(self):
        (m,) = merges("gh pr merge 2>&1 | tail -1")
        self.assertEqual(m.words, ())

    def test_unterminated_quote_does_not_raise(self):
        self.assertEqual(merges("echo 'gh pr merge 1"), [])


if __name__ == "__main__":
    unittest.main()

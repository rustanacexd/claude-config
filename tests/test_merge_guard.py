import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

GUARD = Path(__file__).resolve().parent.parent / "merge_guard.py"

FAKE_GH = textwrap.dedent("""\
    import json, os, sys
    state = json.load(open(os.environ["FAKE_GH_STATE"]))
    with open(os.environ["FAKE_GH_LOG"], "a") as log:
        log.write(json.dumps(sys.argv[1:]) + "\\n")
    args = sys.argv[1:]
    if state.get("fail"):
        sys.exit("gh: boom")
    if args[:2] == ["pr", "view"]:
        target = args[2] if len(args) > 2 and not args[2].startswith("-") else "current"
        print(state["urls"][target])
    elif args[:2] == ["api", "graphql"]:
        after = next((a.split("=", 1)[1] for a in args if a.startswith("after=")), "")
        threads = state["pages"][after or "first"]
        cursor = state.get("next", {}).get(after or "first")
        print(json.dumps({"data": {"repository": {"pullRequest": {
            "isMergeQueueEnabled": state.get("queue", False), "reviewThreads": {
            "nodes": threads,
            "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor}}}}}}))
    """)


def thread(resolved, path="app.py", body="Fix this"):
    return {"isResolved": resolved, "isOutdated": False, "path": path, "line": 3,
            "comments": {"nodes": [{"author": {"login": "bot"}, "body": body}]}}


class MergeGuardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        (self.dir / "bin").mkdir()
        gh = self.dir / "bin/gh"
        gh.write_text(f"#!{sys.executable}\n" + FAKE_GH)
        gh.chmod(0o755)
        self.log = self.dir / "gh.log"
        self.state = {"urls": {"42": "https://github.com/o/r/pull/42",
                               "current": "https://github.com/o/r/pull/7"},
                      "pages": {"first": [thread(True)]}}

    def guard(self, command, tool="Bash"):
        (self.dir / "state.json").write_text(json.dumps(self.state))
        env = dict(os.environ, PATH=f"{self.dir / 'bin'}{os.pathsep}{os.environ['PATH']}",
                   FAKE_GH_STATE=str(self.dir / "state.json"), FAKE_GH_LOG=str(self.log))
        event = {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(self.dir)}
        return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(event),
                              capture_output=True, text=True, env=env, timeout=60)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_other_commands_never_call_gh(self):
        for command in ("ls -la", "gh pr view 42", "git merge main", "gh pr checks 42"):
            self.assertEqual(self.guard(command).returncode, 0, command)
        self.assertEqual(self.calls(), [])

    def test_open_thread_blocks_and_names_it(self):
        self.state["pages"]["first"] = [thread(True), thread(False, "views.py", "Guard the lock")]
        result = self.guard("gh pr merge 42 --squash")
        self.assertEqual(result.returncode, 2)
        self.assertIn("https://github.com/o/r/pull/42 has 1 unresolved", result.stderr)
        self.assertIn("views.py:3 [bot] Guard the lock", result.stderr)

    def test_resolved_threads_allow_the_merge(self):
        self.assertEqual(self.guard("gh pr merge 42 --squash").returncode, 0)

    def test_merge_written_in_other_valid_forms_is_checked(self):
        self.state["pages"]["first"] = [thread(False)]
        for command in ("gh -R o/r pr merge 42", "gh  pr   merge 42",
                        "gh --repo=o/r pr merge 42", "cd x && GH_TOKEN=t gh pr merge 42",
                        "/opt/homebrew/bin/gh pr merge 42", "echo $(gh pr merge 42)"):
            self.assertEqual(self.guard(command).returncode, 2, command)

    def test_repo_flag_before_pr_is_passed_on(self):
        self.guard("gh -R o/r pr merge 42")
        self.assertEqual(self.calls()[0], ["pr", "view", "42", "--repo", "o/r", "--json", "url", "-q", ".url"])

    def test_flag_values_are_not_taken_as_the_target(self):
        for command in ("gh pr merge --match-head-commit abc123 42 --squash",
                        'gh pr merge --body "a; b" 42', "gh pr merge -t subject -b body 42",
                        "gh pr merge --author-email me@x.com -F notes.md 42",
                        "gh pr merge --subject=s 42"):
            self.log.unlink(missing_ok=True)
            self.assertEqual(self.guard(command).returncode, 0, command)
            self.assertEqual(self.calls()[0][:3], ["pr", "view", "42"], command)

    def test_no_target_checks_the_current_branch_pr(self):
        self.state["pages"]["first"] = [thread(False)]
        result = self.guard("gh pr merge --squash")
        self.assertEqual(result.returncode, 2)
        self.assertIn("pull/7", result.stderr)

    def test_open_thread_on_a_later_page_blocks(self):
        self.state["pages"] = {"first": [thread(True)] * 100, "c1": [thread(False, "late.py")]}
        self.state["next"] = {"first": "c1"}
        result = self.guard("gh pr merge 42")
        self.assertEqual(result.returncode, 2)
        self.assertIn("late.py", result.stderr)

    def test_auto_merge_is_refused_because_it_lands_unchecked(self):
        result = self.guard("gh pr merge 42 --auto --squash")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--auto", result.stderr)

    def test_disabling_auto_merge_is_always_allowed(self):
        self.state["pages"]["first"] = [thread(False)]
        self.assertEqual(self.guard("gh pr merge --disable-auto 42").returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_enterprise_host_is_queried_on_that_host(self):
        self.state["urls"]["42"] = "https://git.corp.example/o/r/pull/42"
        result = self.guard("gh pr merge --repo git.corp.example/o/r 42")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--hostname", self.calls()[1])
        self.assertIn("git.corp.example", self.calls()[1])

    def test_unreadable_threads_block(self):
        self.state["fail"] = True
        result = self.guard("gh pr merge 42")
        self.assertEqual(result.returncode, 2)
        self.assertIn("could not read", result.stderr)

    def test_unparseable_merge_command_blocks(self):
        self.assertEqual(self.guard("gh pr merge 42 --body 'unterminated").returncode, 2)

    def test_every_merge_in_one_command_is_checked(self):
        self.state["urls"]["43"] = "https://github.com/o/r/pull/43"
        self.state["pages"]["first"] = [thread(False)]
        self.assertEqual(self.guard("true; gh pr merge 43").returncode, 2)

    def test_powershell_commands_are_checked(self):
        self.state["pages"]["first"] = [thread(False)]
        self.assertEqual(self.guard("gh pr merge 42 --squash; Write-Output done", "PowerShell").returncode, 2)

    def test_line_continuations_are_joined(self):
        self.state["pages"]["first"] = [thread(False)]
        for command in ("gh pr \\\nmerge 42", "gh pr `\nmerge 42", "gh \\\n  pr merge 42"):
            self.assertEqual(self.guard(command).returncode, 2, repr(command))

    def test_unrecognized_pr_merge_text_blocks(self):
        self.assertEqual(self.guard("eval 'gh pr merge 42'").returncode, 2)
        self.assertEqual(self.guard('gh pr create --title "block pr merge"').returncode, 0)

    def test_merge_queue_is_refused_like_auto(self):
        self.state["queue"] = True
        result = self.guard("gh pr merge 42 --squash")
        self.assertEqual(result.returncode, 2)
        self.assertIn("merge queue", result.stderr)

    def test_attached_short_repo_values_are_passed_on(self):
        for command in ("gh -R=o/r pr merge 42", "gh -Ro/r pr merge 42", "gh pr merge 42 -Ro/r",
                        "GH_REPO=o/r gh pr merge 42"):
            self.log.unlink(missing_ok=True)
            self.assertEqual(self.guard(command).returncode, 0, command)
            self.assertEqual(self.calls()[0][:5], ["pr", "view", "42", "--repo", "o/r"], command)

    def test_merge_combined_with_other_commands_blocks(self):
        for command in ("cd /other && gh pr merge 42", "pushd ../b; gh pr merge 42",
                        "Set-Location C:\\b; gh pr merge 42", "cd /other && gh pr merge 42 -R o/r",
                        "export GH_REPO=o/other; gh pr merge 42",
                        "printf '42 --squash\\n' | xargs gh pr merge", "xargs gh pr merge < ids"):
            result = self.guard(command)
            self.assertEqual(result.returncode, 2, command)
            self.assertIn("on its own", result.stderr, command)
        self.assertEqual(self.calls(), [])

    def test_expansions_in_a_merge_block(self):
        for command in ("gh pr merge `42", "gh pr merge $PR", "gh pr merge 42 -R $REPO"):
            self.assertEqual(self.guard(command).returncode, 2, command)
        self.assertEqual(self.calls(), [])

    def test_attached_auto_values_are_read(self):
        self.assertEqual(self.guard("gh pr merge 42 --auto=true").returncode, 2)
        self.assertEqual(self.guard("gh pr merge 42 --auto=false").returncode, 0)
        self.state["pages"]["first"] = [thread(False)]
        self.assertEqual(self.guard("gh pr merge 42 --disable-auto=true").returncode, 0)

    def test_admin_merge_on_a_queue_branch_is_checked_now(self):
        self.state["queue"] = True
        self.assertEqual(self.guard("gh pr merge 42 --admin --squash").returncode, 0)
        self.state["pages"]["first"] = [thread(False)]
        self.assertEqual(self.guard("gh pr merge 42 --admin").returncode, 2)

    def test_gh_name_is_matched_case_insensitively(self):
        self.state["pages"]["first"] = [thread(False)]
        for command in ("GH pr merge 42", "C:\\tools\\GH.EXE pr merge 42", "Gh.exe pr merge 42"):
            self.assertEqual(self.guard(command, "PowerShell").returncode, 2, command)
    def test_repo_flag_at_the_pr_level_is_read(self):
        self.state["pages"]["first"] = [thread(False)]
        self.assertEqual(self.guard("gh pr -R o/r merge 42").returncode, 2)
        self.assertEqual(self.calls()[0][:5], ["pr", "view", "42", "--repo", "o/r"])

    def test_help_is_never_checked(self):
        self.state["fail"] = True
        for command in ("gh pr merge --help", "gh pr merge 42 -h", "gh pr -R o/r merge --help"):
            self.assertEqual(self.guard(command).returncode, 0, command)
        self.assertEqual(self.calls(), [])

    def test_quote_split_and_substituted_names_are_checked(self):
        self.state["pages"]["first"] = [thread(False)]
        for command in ("gh pr m'er'ge 42", 'g"h" pr merge 42', "$(printf gh) pr merge 42",
                        "`printf gh` pr merge 42", '"$GH" pr merge 42'):
            self.assertEqual(self.guard(command).returncode, 2, command)

    def test_option_terminator_marks_the_target(self):
        self.guard("gh pr merge --squash -- -release")
        self.assertEqual(self.calls()[0][:3], ["pr", "view", "-release"])

    def test_quoted_newlines_and_dollars_are_literal(self):
        for command in ('gh pr merge 42 --body "line one\nline two"',
                        "gh pr merge 42 --body 'Fix $PATH handling'"):
            self.log.unlink(missing_ok=True)
            self.assertEqual(self.guard(command).returncode, 0, command)
            self.assertEqual(self.calls()[0][:3], ["pr", "view", "42"], command)

    def test_real_expansions_and_newline_commands_still_block(self):
        for command in ('gh pr merge 42 --body "Fix $PATH"', "gh pr merge 42\nrm -rf x",
                        "gh pr merge $(cat id)"):
            self.assertEqual(self.guard(command).returncode, 2, repr(command))


if __name__ == "__main__":
    unittest.main()

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
        print(json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {
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


if __name__ == "__main__":
    unittest.main()

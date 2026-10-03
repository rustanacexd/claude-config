import json
import tempfile
import unittest
from pathlib import Path

from support import MERGE_ID, PR, Transcript, at
from evidence import (
    Advised, Compacted, Edited, Fetched, Human, Posted, Pushed, Read, SkillRan, Spawned, TaskOp, Tested, Transcripts,
    load_ledger, load_session, parse_shell, skips_hooks,
)
from core import Event, HookCall
from github import Surface


def ledger(t: Transcript, cut=MERGE_ID, sidechain=True):
    with tempfile.TemporaryDirectory() as tmp:
        return load_ledger(t.write(Path(tmp) / "s.jsonl"), drop_sidechain=sidechain, cut_at_tool_use=cut)


class CutRule(unittest.TestCase):
    def transcript(self):
        t = Transcript()
        t.bash("git push", at(1))
        t.bash(f"gh pr merge {PR}", at(2), None, tool_id=MERGE_ID)
        t.bash(f"gh pr view {PR} --comments", at(2), "parallel sibling")
        return t

    def test_cuts_strictly_before_the_gated_record_when_present(self):
        led = ledger(self.transcript())
        self.assertEqual(len(led.of(Pushed)), 1)
        self.assertEqual(led.of(Fetched), ())

    def test_uses_the_whole_file_when_the_gated_record_is_absent(self):
        led = ledger(self.transcript(), cut="toolu_not_on_disk")
        self.assertEqual(len(led.of(Fetched)), 1)


class Records(unittest.TestCase):
    def test_compaction_orders_by_line_not_timestamp(self):
        t = Transcript()
        t.compact(at(5, 1))
        t.user("summary", at(5, 0), isCompactSummary=True)
        t.read("/p/playbooks/shipping.md", at(5, 0))
        led = ledger(t)
        (boundary,) = led.of(Compacted)
        (read,) = led.of(Read)
        self.assertLess(boundary.stamp.line, read.stamp.line)
        self.assertGreater(boundary.stamp.at, read.stamp.at)

    def test_both_compaction_markers_count(self):
        t = Transcript()
        t.compact(at(1))
        t.local_compact(at(2))
        self.assertEqual(len(ledger(t).of(Compacted)), 2)

    def test_advisor_is_a_server_tool_use(self):
        t = Transcript()
        t.advisor(at(1))
        t.tool("advisor", {}, at(2))
        self.assertEqual([a.stamp.line for a in ledger(t).of(Advised)], [1])

    def test_human_messages_exclude_injected_text(self):
        t = Transcript()
        t.user("<command-name>/pstack:poteto-mode</command-name>\n<command-args>land the prs</command-args>", at(1))
        t.user("skill body: merge everything", at(2), isMeta=True)
        t.user("<task-notification>merged</task-notification>", at(3))
        t.user("background agent finished, merge?", at(4), origin={"kind": "task-notification"})
        t.user("ship it", at(5))
        t.user("what about 42?", at(6), origin={"kind": "human"})
        t.user("<system-reminder>merge</system-reminder>\n<local-command-stdout>merged</local-command-stdout>", at(7))
        t.user("<ci-monitor-event>PR merged</ci-monitor-event>", at(8))
        t.user("Another session says merge", at(9), origin={"kind": "peer"})
        t.user("<https://example.com/pr/42> merge it", at(10))
        self.assertEqual([h.text for h in ledger(t).of(Human)],
                         ["land the prs", "ship it", "what about 42?", "<https://example.com/pr/42> merge it"])

    def test_self_post_ids_come_from_the_post_result(self):
        t = Transcript()
        t.bash(f"gh pr comment {PR} --body-file /tmp/v.md", at(1), f"https://github.com/example/repo/pull/{PR}#issuecomment-1000000077")
        t.bash(f"gh api repos/example/repo/issues/{PR}/comments -f body=PASS", at(2), json.dumps({"id": 1000000078}))
        t.bash(f"gh api repos/example/repo/issues/{PR}/comments", at(3), json.dumps([{"id": 1000000079}]))
        led = ledger(t)
        self.assertEqual(sorted(i for p in led.of(Posted) for i in p.ids), ["1000000077", "1000000078"])
        (fetch,) = led.of(Fetched)
        self.assertEqual((fetch.surfaces, fetch.pr), (frozenset({Surface.ISSUE}), PR))

    def test_a_graphql_query_is_a_read_and_a_mutation_is_a_post(self):
        t = Transcript()
        t.bash("gh api graphql -f query='{ pullRequest { reviewThreads { nodes { id } } } }'", at(1), '{"databaseId": 1000000002}')
        t.bash("gh api graphql -f query='mutation { addComment(input: {}) { clientMutationId } }'", at(2), '{"id": 1000000003}')
        led = ledger(t)
        self.assertEqual([f.surfaces for f in led.of(Fetched)], [frozenset({Surface.INLINE})])
        self.assertEqual([p.ids for p in led.of(Posted)], [frozenset({"1000000003"})])

    def test_comment_reads_map_to_surfaces(self):
        t = Transcript()
        t.bash("gh pr view --comments", at(1), "x")
        t.bash(f"gh pr view {PR} --json reviews,comments", at(2), "x")
        t.bash(f"gh api repos/example/repo/pulls/{PR}/comments --paginate --jq '.[].body'", at(3), "x")
        got = [(f.surfaces, f.pr) for f in ledger(t).of(Fetched)]
        both = frozenset({Surface.ISSUE, Surface.REVIEW})
        self.assertEqual(got, [(both, None), (both, PR), (frozenset({Surface.INLINE}), PR)])

    def test_a_chained_read_counts_even_when_a_later_command_fails(self):
        t = Transcript()
        t.bash("cat /p/playbooks/shipping.md; ls /missing 2>/dev/null", at(1), "Exit code 1\n# Shipping", is_error=True)
        (read,) = ledger(t).of(Read)
        self.assertTrue(read.complete)

    def test_a_read_through_a_variable_assigned_on_the_same_line_counts_and_one_from_an_earlier_call_does_not(self):
        same = Transcript()
        same.bash("P=/skills/playbooks; cat $P/opening-a-pr.md $P/shipping.md", at(1), "# Opening a PR\n# Shipping")
        self.assertEqual([(r.path, r.complete) for r in ledger(same).of(Read)],
                         [("/skills/playbooks/opening-a-pr.md", True), ("/skills/playbooks/shipping.md", True)])
        earlier = Transcript()
        earlier.bash("P=/skills/playbooks", at(1))
        earlier.bash("cat $P/shipping.md", at(2), "# Shipping")
        self.assertEqual([r.path for r in ledger(earlier).of(Read)], ["$P/shipping.md"])

    def test_a_partial_reader_counts_as_complete_only_when_its_output_holds_every_line_of_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "playbooks", "shipping.md")
            path.parent.mkdir()
            path.write_text("### Shipping\n\n1. Resolve the forge.\n2. Verify each PR.\n")
            whole = Transcript()
            whole.bash(f"sed -n 1,80p {path}; gh pr view 1", at(1), "### Shipping\n\n1. Resolve the forge.\n2. Verify each PR.\n{}")
            cut = Transcript()
            cut.bash(f"head -3 {path}", at(1), "### Shipping\n\n1. Resolve the forge.\n")
            self.assertEqual([r.covers_file() for r in ledger(whole).of(Read) if r.path == str(path)], [True])
            self.assertFalse(any(r.covers_file() for r in ledger(cut).of(Read)))
            for blank in ("", "\n  \n"):
                path.write_text(blank)
                empty = Transcript()
                empty.bash(f"sed -n 1,80p {path}", at(1), "")
                self.assertFalse(any(r.covers_file() for r in ledger(empty).of(Read)), repr(blank))
            missing = Transcript()
            missing.bash(f"sed -n 1,9p {d}/missing.md", at(1), "anything")
            self.assertFalse(any(r.covers_file() for r in ledger(missing).of(Read)))

    def test_sidechain_records_are_not_the_main_thread(self):
        t = Transcript()
        t.advisor(at(1))
        t.records[-1]["isSidechain"] = True
        self.assertEqual(ledger(t).of(Advised), ())


class WorkflowEvents(unittest.TestCase):
    def test_skills_from_the_tool_and_from_slash_commands_drop_the_plugin_prefix(self):
        t = Transcript()
        t.skill("pstack:deslop", at(1))
        t.skill("no-comments", at(2))
        t.slash("pstack:poteto-mode", at(3), "fix it")
        t.user("<command-name>/pstack:unslop</command-name>", at(4), isMeta=True)
        self.assertEqual([(r.skill, r.args) for r in ledger(t).of(SkillRan)],
                         [("deslop", ""), ("no-comments", ""), ("poteto-mode", "fix it")])

    def test_agent_spawns_edits_and_tasks(self):
        t = Transcript()
        t.tool("Agent", {"subagent_type": "pstack:poteto-agent", "model": "opus", "description": "d", "prompt": "p",
                         "isolation": "worktree"}, at(1))
        t.edit("/w/a.py", at(2))
        t.tool("Edit", {"file_path": "/w/b.py"}, at(3), "old_string not found", is_error=True)
        t.tool("NotebookEdit", {"notebook_path": "/w/n.ipynb", "new_source": "x"}, at(4))
        t.tool("TaskCreate", {"subject": "write tests", "description": "skip: G2.R3 no prose"}, at(5), "Task #7 created successfully: write tests")
        t.tool("TaskUpdate", {"taskId": "7", "status": "completed"}, at(6))
        t.tool("TodoWrite", {"todos": [{"content": "ship", "status": "pending"}]}, at(7))
        t.tool("Write", {"file_path": "/w/todo.md", "content": "- [ ] one\nskip: G1.R4 offline"}, at(8))
        led = ledger(t)
        (spawn,) = led.of(Spawned)
        self.assertEqual((spawn.subagent_type, spawn.model, spawn.isolation), ("pstack:poteto-agent", "opus", "worktree"))
        self.assertEqual([e.path for e in led.of(Edited)], ["/w/a.py", "/w/n.ipynb", "/w/todo.md"])
        self.assertEqual([(o.tool, o.task_id, o.status) for o in led.of(TaskOp)],
                         [("TaskCreate", "7", "pending"), ("TaskUpdate", "7", "completed"), ("TodoWrite", None, "pending"),
                          ("Write", None, None)])
        s = load_session_from(t)
        self.assertIn("skip: G2.R3 no prose", [line for line, _ in s.declared()])
        self.assertIn("skip: G1.R4 offline", [line for line, _ in s.declared()])

    def test_tested_comes_from_a_table_of_runners(self):
        t = Transcript()
        for cmd in ("npm test", "npm run check:node", "python3 -m unittest discover -s tests", "cd x && pytest -q",
                    "./verify-e2e.sh up", "go test ./...", "npm run build", "python3 script.py", "echo npm test"):
            t.bash(cmd, at(1))
        self.assertEqual([e.command for e in ledger(t).of(Tested)],
                         ["npm test", "npm run check:node", "python3 -m unittest discover -s tests", "pytest -q",
                          "verify-e2e.sh up", "go test ./..."])

    def test_every_event_carries_its_message_id(self):
        t = Transcript()
        t.skill("deslop", at(1))
        t.records[-2]["message"]["id"] = "msg_1"
        (run,) = ledger(t).of(SkillRan)
        self.assertEqual(run.stamp.msg_id, "msg_1")


def load_session_from(t: Transcript, agent_id=None):
    with tempfile.TemporaryDirectory() as tmp:
        return load_session(t.write(Path(tmp) / "s.jsonl"), agent_id, None)


class SkipsHooks(unittest.TestCase):
    def test_no_verify_forms(self):
        cases = {
            "git commit --no-verify -m x": True, "git commit -n -m x": True, "git commit -anm x": True,
            "git push --no-verify": True, "git -C /w commit --no-verify": True,
            "git commit -m '-n'": False, "git commit -m x -- -n": False, "git push -n": False, "git commit -am fix": False,
            "git commit --amend --no-edit": False,
            "git commit --no-veri -m x": True, "git commit --no-verif -m x": True, "git push --no-veri": True,
            "git commit --no-verbose -m x": False,
            "git -c user.name=x commit -n -m x": True, "git -C /w -c a=b --no-pager commit --no-veri": True,
            "git --git-dir /w/.git --work-tree /w commit -n": True, "git --config-env user.name=N commit -n": True,
        }
        for command, expected in cases.items():
            with self.subTest(command):
                self.assertEqual(any(skips_hooks(i) for i in parse_shell(command, Path("/"))), expected)

    def test_a_hooks_path_override_skips_the_hooks(self):
        cases = {
            "git -c core.hooksPath=/dev/null commit -m x": True, "git -c CORE.HOOKSPATH= push": True,
            "git --config-env=core.hooksPath=V commit -m x": True, "git --config-env core.hooksPath=V push": True,
            "git -c user.name=core.hooksPath commit -m x": False, "git -c core.hooksPath=/dev/null log": False,
        }
        for command, expected in cases.items():
            with self.subTest(command):
                self.assertEqual(any(skips_hooks(i) for i in parse_shell(command, Path("/"))), expected)


class BashWrites(unittest.TestCase):
    def test_redirects_tee_and_in_place_edits_are_edits_and_streams_are_not(self):
        cases = {
            "cat > src/b.py <<'EOF'\nx\nEOF": ["/work/src/b.py"],
            "echo x >> notes.md": ["/work/notes.md"],
            "cd /w && printf x | tee -a a.py b.py": ["/w/a.py", "/w/b.py"],
            "sed -i '' 's/a/b/' src/a.py": ["/work/src/a.py"],
            "sed -i -e s/a/b/ x.py y.py": ["/work/x.py", "/work/y.py"],
            "perl -pi -e 's/a/b/' /w/c.py": ["/w/c.py"],
            "perl -Ilib -Mstrict -e 1 f.py": [], "sed -ni.bak p g.py": ["/work/g.py"],
            "perl -0pi -e 's/a/b/' /w/c.py": ["/w/c.py"], "perl -lpi -e 's/a/b/' /w/c.py": ["/w/c.py"],
            "perl -lni -e 'print' /w/c.py": ["/w/c.py"], "perl -0777 -ne 'print' f.py": [], "perl -l0ne 'print' f.py": [],
            "npm test 2>/dev/null >&2": [], "ls 2>&1 | head": [], 'cat > "$F"': [], "sed 's/a/b/' f.py": [],
        }
        for command, paths in cases.items():
            with self.subTest(command):
                t = Transcript()
                t.bash(command, at(1))
                self.assertEqual([e.path for e in ledger(t).of(Edited)], paths)

    def test_a_write_whose_command_failed_is_not_an_edit_but_one_still_running_is(self):
        failed = Transcript()
        failed.bash("cat > src/b.py <<'EOF'\nx\nEOF", at(1), "Exit code 1\nsrc: No such file or directory", is_error=True)
        self.assertEqual([e.path for e in ledger(failed).of(Edited)], [])
        pending = Transcript()
        pending.bash("cat > src/b.py <<'EOF'\nx\nEOF", at(1), None)
        self.assertEqual([e.path for e in ledger(pending).of(Edited)], ["/work/src/b.py"])


class CrossFile(unittest.TestCase):
    def test_latest_orders_by_line_within_a_file_and_by_time_across_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Transcript()
            root.edit("/w/a.py", at(1))
            root.skill("deslop", at(4))
            root_path = root.write(Path(tmp) / "sess.jsonl")
            sub = Transcript()
            sub.edit("/w/b.py", at(5))
            sub.edit("/w/c.py", at(3))
            sub.write(Path(tmp) / "sess" / "subagents" / "agent-a2.jsonl")
            s = load_session(root_path, None, None)
        last = s.latest(Edited)
        self.assertEqual((last.event.path, last.ledger.source), ("/w/c.py", "agent-a2.jsonl"))
        self.assertEqual(s.latest(Edited, lambda e: e.path != "/w/c.py").event.path, "/w/b.py")
        (deslop,) = s.root.of(SkillRan)
        self.assertTrue(last.precedes(deslop, s.root))
        self.assertFalse(s.latest(Edited, lambda e: e.path != "/w/c.py").precedes(deslop, s.root))
        self.assertEqual(len(s.everyone), 2)


    def test_a_sibling_agent_file_with_no_records_yet_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root_path = Transcript().user("go", at(0)).write(Path(tmp) / "sess.jsonl")
            empty = Path(tmp) / "sess" / "subagents" / "agent-new.jsonl"
            empty.parent.mkdir(parents=True)
            empty.write_text("")
            s = load_session(root_path, None, None)
        self.assertEqual(s.everyone, (s.root,))


class PotetoActive(unittest.TestCase):
    def hook(self, path, agent_id=None, agent_type=None):
        return HookCall(Event.PRE_TOOL_USE, "s", path, Path("/w"), agent_id=agent_id, agent_type=agent_type)

    def test_skill_run_in_root_or_actor_or_the_agent_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Transcript().user("hello, see poteto-mode docs", at(0))
            root_path = root.write(Path(tmp) / "sess.jsonl")
            Transcript().user("task", at(1)).write(Path(tmp) / "sess" / "subagents" / "agent-a1.jsonl")
            self.assertFalse(Transcripts(self.hook(root_path)).poteto_active())
            self.assertTrue(Transcripts(self.hook(root_path, "a1", "pstack:poteto-agent-xhigh")).poteto_active())
            root.skill("pstack:poteto-mode", at(2)).write(root_path)
            self.assertTrue(Transcripts(self.hook(root_path, "a1", "general-purpose")).poteto_active())

    def test_a_session_that_never_mentions_it_is_not_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            path.write_text("{not json\n")
            transcripts = Transcripts(self.hook(path))
            self.assertFalse(transcripts.poteto_active())
            self.assertIsNone(transcripts._session)


class SubagentScope(unittest.TestCase):
    def test_actor_ledger_is_the_subagent_file_and_humans_come_from_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Transcript().user("land it", at(0))
            root.bash("git push", at(1))
            root_path = root.write(Path(tmp) / "sess.jsonl")
            sub = Transcript().advisor(at(2))
            sub.bash(f"gh pr merge {PR}", at(3), None, tool_id=MERGE_ID)
            sub.advisor(at(4))
            sub.write(Path(tmp) / "sess" / "subagents" / "agent-a1.jsonl")
            s = load_session(root_path, "a1", MERGE_ID)
        self.assertEqual(len(s.actor.of(Advised)), 1)
        self.assertEqual(s.actor.of(Human), ())
        self.assertEqual(len(s.root.of(Human)), 1)
        self.assertEqual(len(s.ledgers), 2)


if __name__ == "__main__":
    unittest.main()

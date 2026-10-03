import json
import tempfile
import unittest
from pathlib import Path

from support import MERGE_ID, PR, Transcript, at
from evidence import Advised, Compacted, Fetched, Human, Posted, Pushed, Read, load_ledger, load_session
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

    def test_sidechain_records_are_not_the_main_thread(self):
        t = Transcript()
        t.advisor(at(1))
        t.records[-1]["isSidechain"] = True
        self.assertEqual(ledger(t).of(Advised), ())


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

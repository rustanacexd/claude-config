import json
import os
import tempfile
import unittest
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional, Tuple
from unittest import mock

from support import Transcript, at, env, flagged_ids, forbidden_runner, said
from test_agent_evidence import send, spawn
from test_shim import run_shim
import evidence
import g8_worktree
import hook
from core import Mode

AGENT = "a0000000000000001"
GATED = "toolu_gated"


@dataclass(frozen=True)
class Tree:
    main: Path
    wt: Path
    other: Path


def tree(tmp: Path) -> Tree:
    main, wt, other = tmp / "repo", tmp / "repo.feature", tmp / "repo.other"
    (main / ".git").mkdir(parents=True)
    for linked in (wt, other):
        (linked / "src").mkdir(parents=True)
        (linked / ".git").write_text(f"gitdir: {main}/.git/worktrees/{linked.name}\n")
    return Tree(main, wt, other)


Step = Callable[[Transcript, Tree], None]


@dataclass(frozen=True)
class WtCase:
    steps: Tuple[Tuple[str, Step], ...]
    tool: str = "Edit"
    target: Callable[[Tree], dict] = lambda tr: {"file_path": f"{tr.wt}/src/a.py", "old_string": "a", "new_string": "b"}
    cwd: Callable[[Tree], Path] = lambda tr: tr.main
    agent_id: Optional[str] = None


GREEN = WtCase(steps=(
    ("spawn", lambda t, tr: spawn(t, at(1), "msg_1", prompt=f"Work in {tr.wt} on branch feature.", agent_id=AGENT)),
    ("pgrep", lambda t, tr: t.bash(f"pgrep -fl {tr.wt}", at(2), "")),
))


def run_wt(case: WtCase, tmp: Path, mode: Mode = Mode.BLOCK):
    tr = tree(tmp)
    t = Transcript()
    for _, step in case.steps:
        step(t, tr)
    inp = case.target(tr)
    t.tool(case.tool, inp, at(5), None, tool_id=GATED)
    d = {"session_id": "sess-1", "transcript_path": str(t.write(tmp / "session.jsonl")), "cwd": str(case.cwd(tr)),
         "hook_event_name": "PreToolUse", "tool_name": case.tool, "tool_input": inp, "tool_use_id": GATED}
    if case.agent_id:
        d.update(agent_id=case.agent_id, agent_type="general-purpose")
        Transcript().write(tmp / "session" / "subagents" / f"agent-{case.agent_id}.jsonl")
    return hook.run(json.dumps(d), env(forbidden_runner, mode))


def plus(case, *steps):
    return replace(case, steps=case.steps + steps)


def without(case, *names):
    return replace(case, steps=tuple(s for s in case.steps if s[0] not in names))


def bash(command: Callable[[Tree], str]) -> dict:
    return dict(tool="Bash", target=lambda tr: {"command": command(tr)})


def settings_write(path: Callable[[Tree], str]) -> dict:
    return dict(tool="Write", target=lambda tr: {"file_path": path(tr), "content": "{}"}, steps=())


R1, R2 = frozenset({"G8.R1"}), frozenset({"G8.R2"})
MUTATIONS = (
    ("no pgrep", R1, without(GREEN, "pgrep")),
    ("pgrep before the spawn", R1, replace(GREEN, steps=tuple(reversed(GREEN.steps)))),
    ("pgrep of another path", R1, replace(GREEN, steps=GREEN.steps[:1] + (("pgrep", lambda t, tr: t.bash(f"pgrep -fl {tr.other}", at(2))),))),
    ("pgrep in the same command as the write", R1,
     replace(without(GREEN, "pgrep"), **bash(lambda tr: f"pgrep -fl {tr.wt}; git -C {tr.wt} reset --hard"))),
    ("the agent was messaged after the pgrep", R1, plus(GREEN, ("send", lambda t, tr: send(t, AGENT, at(3))))),
    ("the agent was resumed by name after the pgrep", R1, plus(GREEN, ("send", lambda t, tr: send(t, "worker", at(3), resumed=AGENT)))),
    ("git commit after cd", R1, replace(without(GREEN, "pgrep"), **bash(lambda tr: f"cd {tr.wt} && git commit -m x"))),
    ("rm -rf of a path inside it", R1, replace(without(GREEN, "pgrep"), **bash(lambda tr: f"rm -rf {tr.wt}/src"))),
    ("the prompt names the real path", R1,
     replace(GREEN, steps=(("spawn", lambda t, tr: spawn(t, at(1), "msg_1", prompt=f"Work in {os.path.realpath(tr.wt)}.", agent_id=AGENT)),))),
    ("git reset after a relative cd", R1, replace(without(GREEN, "pgrep"), **bash(lambda tr: f"cd ../{tr.wt.name} && git reset --hard"))),
    ("git -C with a relative path", R1, replace(without(GREEN, "pgrep"), **bash(lambda tr: f"git -C ../{tr.wt.name} checkout -- ."))),
    ("a relative file_path into it", R1, replace(without(GREEN, "pgrep"), target=lambda tr: {"file_path": f"../{tr.wt.name}/src/a.py"})),
    ("a settings.json write under .claude", R2, WtCase(**settings_write(lambda tr: f"{tr.main}/.claude/settings.json"))),
    ("a redirect into settings.json", R2, WtCase(steps=(), **bash(lambda tr: f"echo '{{}}' > {tr.main}/.claude/settings.json"))),
    ("a relative redirect into settings.json from the main checkout", R2, WtCase(steps=(), **bash(lambda tr: "echo '{}' > .claude/settings.json"))),
    ("a relative redirect into it after a cd", R1,
     replace(without(GREEN, "pgrep"), **bash(lambda tr: f"cd ../{tr.wt.name} && echo x > settings.local.json"))),
    ("tee -p into settings.json", R2, WtCase(steps=(), **bash(lambda tr: f"echo '{{}}' | tee -p {tr.main}/.claude/settings.json"))),
    ("sed -i on settings.local.json", R2,
     WtCase(steps=(), **bash(lambda tr: f"sed -i '' 's/a/b/' {tr.main}/.claude/settings.local.json"))),
)


class WorktreeGate(unittest.TestCase):
    def test_green_allows_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_wt(GREEN, Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_each_mutation_flags_exactly_its_requirement(self):
        for name, expected, case in MUTATIONS:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                outcome = run_wt(case, Path(tmp))
                self.assertEqual(flagged_ids(outcome), expected, outcome.stderr or outcome.stdout)
                self.assertEqual(outcome.exit_code, 2 if expected == R1 else 0)

    def test_a_pgrep_after_the_message_allows_again(self):
        case = plus(GREEN, ("send", lambda t, tr: send(t, AGENT, at(3))), ("again", lambda t, tr: t.bash(f"pgrep -f {tr.wt}", at(4))))
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_wt(case, Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_a_message_to_another_agent_does_not_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_wt(plus(GREEN, ("send", lambda t, tr: send(t, "a0000000000000009", at(3)))), Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stderr), (0, ""))

    def test_the_block_names_the_worktree_and_the_pgrep_to_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_wt(without(GREEN, "pgrep"), Path(tmp))
            self.assertIn(f"`pgrep -fl {Path(tmp) / 'repo.feature'}` as its own Bash call", outcome.stderr)

    def test_writes_that_never_reach_r1(self):
        cases = (
            ("in the session's own worktree", replace(without(GREEN, "pgrep"), cwd=lambda tr: tr.wt / "src")),
            ("by the subagent that holds it", replace(without(GREEN, "pgrep"), agent_id=AGENT)),
            ("into a worktree no agent was handed", replace(without(GREEN, "pgrep"),
                                                             target=lambda tr: {"file_path": f"{tr.other}/src/a.py"})),
            ("into the main checkout", replace(without(GREEN, "pgrep"), target=lambda tr: {"file_path": f"{tr.main}/a.py"})),
            ("into a main checkout an agent was handed", WtCase(
                steps=(("spawn", lambda t, tr: spawn(t, at(1), "msg_1", prompt=f"Read {tr.main} only.", agent_id=AGENT)),),
                target=lambda tr: {"file_path": f"{tr.main}/a.py"}, cwd=lambda tr: tr.wt)),
            ("a read-only git command", replace(without(GREEN, "pgrep"), **bash(lambda tr: f"git -C {tr.wt} status && rm -f /tmp/x"))),
        )
        for name, case in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                outcome = run_wt(case, Path(tmp))
                self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_an_ordinary_edit_never_reads_the_transcript(self):
        case = replace(without(GREEN, "pgrep"), target=lambda tr: {"file_path": f"{tr.main}/src/a.py"})
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(g8_worktree, "_text", side_effect=AssertionError("read")), \
                mock.patch.object(evidence, "load_session", side_effect=AssertionError("parsed")):
            outcome = run_wt(case, Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_a_worktree_no_prompt_names_is_never_parsed(self):
        case = replace(without(GREEN, "pgrep"), target=lambda tr: {"file_path": f"{tr.other}/src/a.py"})
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(evidence, "load_session", side_effect=AssertionError("parsed")):
            outcome = run_wt(case, Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_a_sibling_path_with_a_shared_prefix_is_not_a_mention(self):
        case = replace(without(GREEN, "pgrep"), steps=(("spawn", lambda t, tr: spawn(t, at(1), "msg_1", prompt=f"Use {tr.wt}-old.", agent_id=AGENT)),))
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_wt(case, Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stderr), (0, ""))

    def test_update_config_licenses_a_settings_edit(self):
        case = WtCase(steps=(("skill", lambda t, tr: t.skill("update-config", at(1))),),
                      **{k: v for k, v in settings_write(lambda tr: f"{tr.main}/.claude/settings.json").items() if k != "steps"})
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_wt(case, Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_a_settings_named_file_outside_claude_is_not_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_wt(WtCase(**settings_write(lambda tr: f"{tr.main}/src/settings.json")), Path(tmp))
        self.assertEqual((outcome.exit_code, outcome.stdout, outcome.stderr), (0, "", ""))

    def test_a_home_relative_prompt_and_write_are_the_same_worktree(self):
        case = WtCase(steps=(("spawn", lambda t, tr: spawn(t, at(1), "msg_1", prompt="Work in ~/repo.feature.", agent_id=AGENT)),),
                      tool="Write", target=lambda tr: {"file_path": "~/repo.feature/src/a.py", "content": "x"})
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(g8_worktree, "HOME", Path(tmp)), \
                mock.patch.dict(os.environ, {"HOME": tmp}):
            outcome = run_wt(case, Path(tmp))
        self.assertEqual(flagged_ids(outcome), R1, outcome.stderr)

    def test_a_relative_path_resolves_under_a_symlinked_parent(self):
        for command in ("cd ../repo.feature && git reset --hard", "git -C ../repo.feature checkout -- ."):
            with self.subTest(command), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "real").mkdir()
                os.symlink(Path(tmp) / "real", Path(tmp) / "link")
                outcome = run_wt(replace(without(GREEN, "pgrep"), **bash(lambda tr, c=command: c)), Path(tmp) / "link")
                self.assertEqual(flagged_ids(outcome), R1, outcome.stderr)

    def test_the_prompt_and_the_write_may_spell_the_temp_directory_either_way(self):
        def named(prompt_path, write_path):
            return WtCase(steps=(("spawn", lambda t, tr: spawn(t, at(1), "msg_1", prompt=f"Work in {prompt_path(tr)}.", agent_id=AGENT)),),
                          tool="Write", target=lambda tr: {"file_path": f"{write_path(tr)}/src/a.py", "content": "x"})
        for prompt, write in ((lambda tr: tr.wt, lambda tr: os.path.realpath(tr.wt)), (lambda tr: os.path.realpath(tr.wt), lambda tr: tr.wt)):
            with self.subTest(prompt=prompt), tempfile.TemporaryDirectory() as tmp:
                outcome = run_wt(named(prompt, write), Path(tmp))
                self.assertEqual(flagged_ids(outcome), R1, outcome.stderr)

    def test_a_settings_file_reached_through_the_live_symlink_is_config(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(g8_worktree, "HOME", Path(tmp)):
            (Path(tmp) / "dotfiles").mkdir()
            (Path(tmp) / "dotfiles" / "settings.json").write_text("{}")
            (Path(tmp) / ".claude").mkdir()
            os.symlink(Path(tmp) / "dotfiles" / "settings.json", Path(tmp) / ".claude" / "settings.json")
            outcome = run_wt(WtCase(**settings_write(lambda tr: f"{tmp}/dotfiles/settings.json")), Path(tmp))
        self.assertEqual(flagged_ids(outcome), R2, outcome.stdout)

    def test_warn_mode_lets_the_write_run_with_the_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = run_wt(without(GREEN, "pgrep"), Path(tmp), Mode.WARN)
        self.assertEqual(outcome.exit_code, 0)
        self.assertIn("FAIL G8.R1", said(outcome))


class ShimFastPath(unittest.TestCase):
    def test_words_that_contain_rm_do_not_start_python(self):
        for command in ("npm run format", "perform the term", "git status"):
            with self.subTest(command):
                self.assertEqual(run_shim(command, python_exit=2)[:2], (0, False))

    def test_recursive_and_forced_rm_in_every_spelling_starts_python(self):
        for command in ("rm -rf /w/x", "rm -Rf /w/x", "rm -R /w/x", "rm --recursive --force /w/x", "rm --force /w/x"):
            with self.subTest(command):
                self.assertEqual(run_shim(command, python_exit=0)[:2], (0, True))

    def test_edit_tools_always_start_python(self):
        for matcher in ("Edit|Write|MultiEdit", "Skill|Agent"):
            with self.subTest(matcher):
                self.assertTrue(run_shim("", python_exit=0, args=("PreToolUse", matcher))[1])


if __name__ == "__main__":
    unittest.main()

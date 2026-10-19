import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from portable import sync
from portable.manage import refresh


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "skills/shared").mkdir(parents=True)
        (self.repo / "skills/shared/SKILL.md").write_text("shared skill")
        (self.repo / "settings.json").write_text("{}")
        (self.repo / "codex").mkdir()
        (self.repo / "codex/config.template.toml").write_text("")
        self.manifest = {"assets": [{"source": "skills/shared",
                                     "destination": "skills/shared",
                                     "apps": ["claude", "codex"]}]}
        (self.repo / "SKILLS.md").write_text(
            "npx skills add owner/tools --skill upstream -g -a claude-code codex --copy -y\n"
        )
        self.homes = {app: Path(self.temp.name) / app for app in ("claude", "codex")}
        for home in self.homes.values():
            (home / "skills/shared").mkdir(parents=True)
            (home / "skills/shared/SKILL.md").write_text("shared skill")
        self.agents = Path(self.temp.name) / "agents/skills"
        self.agents.mkdir(parents=True)

    def check(self, plugins=(), inventory=None):
        return sync.check_local(self.repo, self.manifest, list(plugins), self.homes,
                                self.agents, inventory or {"claude": {}, "codex": {}})

    def test_unrecorded_installed_skill_fails_until_declared(self):
        skill = self.agents / "new-diagram"
        skill.mkdir()
        (skill / "SKILL.md").write_text("new diagram skill")
        self.assertEqual(self.check(), [
            "codex: skill new-diagram is not recorded; add it to SKILLS.md or portable.json"
        ])
        with (self.repo / "SKILLS.md").open("a") as guide:
            guide.write("npx skills add owner/diagram --skill new-diagram -g -a codex --copy -y\n")
        self.assertEqual(self.check(), [])

    def test_unrecorded_plugin_is_reported_and_local_enablement_is_allowed(self):
        declared = [{"app": "claude", "id": "known@market", "enabled": True}]
        inventory = {"claude": {"known@market": {"enabled": False},
                                 "new@market": {"enabled": True}}, "codex": {}}
        self.assertEqual(self.check(declared, inventory), [
            "claude: plugin new@market is not recorded in plugins.json",
        ])

    def refreshed_claude(self, settings):
        (self.repo / "portable.json").write_text(json.dumps(dict(self.manifest, schema=1)))
        (self.repo / "plugins.json").write_text('{"schema":1,"plugins":[]}')
        (self.repo / "settings.json").write_text(json.dumps(settings))
        home = self.homes["claude"]
        (home / "portable.local.json").write_text('{"env":{"ANTHROPIC_AUTH_TOKEN":"local-token"}}')
        refresh(self.repo, {"claude": home}, ["claude"])
        return home

    def edit_live(self, home, change):
        live = json.loads((home / "settings.json").read_text())
        change(live)
        (home / "settings.json").write_text(json.dumps(live))

    def test_live_setting_edit_is_reported_until_recorded(self):
        home = self.refreshed_claude({"model": "opus"})
        self.assertEqual(self.check(), [])
        (self.repo / "settings.json").write_text('{"model": "fable"}')
        self.assertEqual(self.check(), [])
        self.edit_live(home, lambda live: live.update(
            model="sonnet", enabledPlugins={"local@market": True}))
        self.assertEqual(self.check(), [
            "claude: setting model differs from settings.json; copy it into the "
            f"repository or {home / 'portable.local.json'}"
        ])
        (self.repo / "settings.json").write_text('{"model": "sonnet"}')
        self.assertEqual(self.check(), [])

    def merge_guards(self, home):
        live = json.loads((home / "settings.json").read_text())
        return [hook for entry in live.get("hooks", {}).get("PreToolUse", [])
                for hook in entry["hooks"] if "merge_guard.py" in json.dumps(hook)]

    def test_merge_guard_blocks_on_failure_for_bash_and_powershell(self):
        home = self.refreshed_claude({})
        guards = self.merge_guards(home)
        self.assertEqual(sorted(hook["if"].split("(")[0] for hook in guards), ["Bash", "PowerShell"])
        self.assertTrue(all(hook["onFailure"] == "block" for hook in guards))
        self.assertEqual(self.check(), [])

    def test_merge_guard_survives_local_profile_hooks(self):
        local_hook = {"matcher": "Edit", "hooks": [{"type": "command", "command": "fmt"}]}
        (self.repo / "portable.json").write_text(json.dumps(dict(self.manifest, schema=1)))
        (self.repo / "plugins.json").write_text('{"schema":1,"plugins":[]}')
        home = self.homes["claude"]
        (home / "portable.local.json").write_text(json.dumps({"hooks": {"PreToolUse": [local_hook]}}))
        refresh(self.repo, {"claude": home}, ["claude"])
        live = json.loads((home / "settings.json").read_text())
        self.assertIn(local_hook, live["hooks"]["PreToolUse"])
        self.assertEqual(len(self.merge_guards(home)), 2)
        self.assertEqual(self.check(), [])
        refresh(self.repo, {"claude": home}, ["claude"])
        self.assertEqual(len(self.merge_guards(home)), 2)

    def test_merge_guard_survives_live_hook_edits(self):
        home = self.refreshed_claude({})
        local_hook = {"matcher": "Edit", "hooks": [{"type": "command", "command": "fmt"}]}
        self.edit_live(home, lambda live: live["hooks"].update(PreToolUse=[local_hook]))
        refresh(self.repo, {"claude": home}, ["claude"])
        live = json.loads((home / "settings.json").read_text())
        self.assertIn(local_hook, live["hooks"]["PreToolUse"])
        self.assertEqual(len(self.merge_guards(home)), 2)

    def test_merge_guard_refresh_keeps_other_handlers_in_its_entry(self):
        home = self.refreshed_claude({})
        extra = {"type": "command", "command": "audit"}
        self.edit_live(home, lambda live: live["hooks"]["PreToolUse"][-1]["hooks"].append(extra))
        refresh(self.repo, {"claude": home}, ["claude"])
        live = json.loads((home / "settings.json").read_text())
        handlers = [h for entry in live["hooks"]["PreToolUse"] for h in entry["hooks"]]
        self.assertIn(extra, handlers)
        self.assertEqual(len(self.merge_guards(home)), 2)

    def test_drifted_secret_is_reported_without_its_value(self):
        home = self.refreshed_claude({})
        self.edit_live(home, lambda live: live["env"].update(ANTHROPIC_AUTH_TOKEN="rotated-token"))
        issues = self.check()
        self.assertEqual(issues, [
            "claude: setting env.ANTHROPIC_AUTH_TOKEN differs from settings.json; copy it into "
            f"the repository or {home / 'portable.local.json'}"
        ])
        self.assertNotIn("rotated-token", issues[0])

    def test_local_edit_to_managed_skill_is_reported(self):
        (self.homes["codex"] / "skills/shared/SKILL.md").write_text("local edit")
        self.assertEqual(self.check(), [
            "codex: skills/shared/SKILL.md differs from skills/shared/SKILL.md in the repository; "
            "edit the repository copy and run refresh"
        ])

    def test_edited_copy_of_managed_skill_outside_the_home_is_reported(self):
        (self.agents / "shared").mkdir()
        (self.agents / "shared/SKILL.md").write_text("agents copy")
        self.assertEqual(self.check(), [
            "codex: skill shared differs from skills/shared; copy the intended edits into the repository"
        ])

    def add_instructions(self):
        (self.repo / "CLAUDE.md").write_text("claude instructions")
        (self.repo / "codex/AGENTS.md").write_text("codex instructions")
        self.manifest["assets"] += [
            {"source": "CLAUDE.md", "destination": "CLAUDE.md", "apps": ["claude"]},
            {"source": "codex/AGENTS.md", "destination": "AGENTS.md", "apps": ["codex"]},
        ]
        (self.repo / "portable.json").write_text(json.dumps(dict(self.manifest, schema=1)))
        (self.repo / "plugins.json").write_text('{"schema":1,"plugins":[]}')

    def refreshed_instructions(self):
        self.add_instructions()
        refresh(self.repo, self.homes, ["claude", "codex"])

    def test_refreshed_files_pass_before_refresh_after_it_and_while_the_repository_is_ahead(self):
        self.add_instructions()
        self.assertEqual(self.check(), [])
        refresh(self.repo, self.homes, ["claude", "codex"])
        self.assertEqual(self.check(), [])
        (self.repo / "CLAUDE.md").write_text("newer claude instructions")
        (self.repo / "skills/shared/SKILL.md").write_text("newer shared skill")
        self.assertEqual(self.check(), [])
        refresh(self.repo, self.homes, ["claude", "codex"])
        self.assertEqual((self.homes["claude"] / "CLAUDE.md").read_text(), "newer claude instructions")
        self.assertEqual(self.check(), [])

    def test_edited_claude_instructions_are_reported_until_recorded(self):
        self.refreshed_instructions()
        (self.homes["claude"] / "CLAUDE.md").write_text("edited in place")
        self.assertEqual(self.check(), [
            "claude: CLAUDE.md differs from CLAUDE.md in the repository; "
            "edit the repository copy and run refresh"
        ])
        (self.repo / "CLAUDE.md").write_text("edited in place")
        refresh(self.repo, self.homes, ["claude", "codex"])
        self.assertEqual(self.check(), [])

    def test_edited_codex_instructions_are_reported(self):
        self.refreshed_instructions()
        (self.homes["codex"] / "AGENTS.md").write_text("edited in place")
        self.assertEqual(self.check(), [
            "codex: AGENTS.md differs from codex/AGENTS.md in the repository; "
            "edit the repository copy and run refresh"
        ])

    def test_deleted_instructions_and_added_skill_files_are_reported(self):
        self.refreshed_instructions()
        (self.homes["claude"] / "CLAUDE.md").unlink()
        (self.homes["codex"] / "skills/shared/notes.md").write_text("local notes")
        self.assertEqual(self.check(), [
            "claude: CLAUDE.md was deleted; copy CLAUDE.md from the repository to restore it, "
            "or remove it from the repository",
            "codex: skills/shared/notes.md is not in the repository; add it as "
            "skills/shared/notes.md and run refresh, or delete it",
        ])

    def test_upstream_and_system_skills_do_not_require_vendoring(self):
        for name in ("upstream", ".system"):
            skill = self.agents / name
            skill.mkdir()
            (skill / "SKILL.md").write_text("upstream")
        self.assertEqual(self.check(), [])

    def test_ci_rejects_repository_skill_missing_from_manifest(self):
        skill = self.repo / "codex/skills/forgotten"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("forgotten skill")
        self.assertEqual(sync.check_repository(self.repo, self.manifest), [
            "codex/skills/forgotten/SKILL.md is not covered by portable.json"
        ])

    def test_pending_shared_changes_block_push(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
            subprocess.run(["git", "-C", str(self.repo), "config", key, value], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "initial"], check=True)
        self.assertEqual(sync.check_committed(self.repo), [])
        (self.repo / "SKILLS.md").write_text("not committed")
        self.assertEqual(sync.check_committed(self.repo), [
            "Shared setup has uncommitted changes; commit them before pushing"
        ])

    def test_push_of_a_different_revision_is_rejected(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
            subprocess.run(["git", "-C", str(self.repo), "config", key, value], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "initial"], check=True)
        head = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.assertEqual(sync.check_push_target(self.repo, f"refs/heads/main {head} refs/heads/main {'0' * 40}"), [])
        self.assertEqual(sync.check_push_target(self.repo, f"refs/heads/old {'1' * 40} refs/heads/old {'0' * 40}"), [
            "Push the checked-out setup commit so the sync check covers the revision being pushed"
        ])

    def test_real_cli_repository_check(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / "manage.py"), "check-sync", "--repo-only"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Repository sync declarations OK", result.stdout)

    def test_git_push_blocks_an_unrecorded_local_skill(self):
        source = Path(__file__).resolve().parents[1]
        (self.repo / "portable.json").write_text(json.dumps(dict(self.manifest, schema=1)))
        (self.repo / "plugins.json").write_text('{"schema":1,"plugins":[]}')
        (self.repo / "manage.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            f"sys.path.insert(0, {str(source)!r})\n"
            "import manage\nmanage.REPO = Path(__file__).resolve().parent\n"
            "manage.installed = lambda app, home: {}\n"
            f"sys.argv.extend(['--home', {self.temp.name!r}])\n"
            "raise SystemExit(manage.main())\n"
        )
        hook = self.repo / ".githooks/pre-push"
        hook.parent.mkdir()
        hook.write_bytes((source / ".githooks/pre-push").read_bytes())
        hook.chmod(0o755)
        remote = Path(self.temp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        def git(*args):
            return subprocess.run(["git", "-C", str(self.repo), *args],
                                  capture_output=True, text=True)
        self.assertEqual(git("init", "-q").returncode, 0)
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com"),
                           ("core.hooksPath", ".githooks")):
            self.assertEqual(git("config", key, value).returncode, 0)
        self.assertEqual(git("add", ".").returncode, 0)
        self.assertEqual(git("commit", "-qm", "initial").returncode, 0)
        first = git("rev-parse", "HEAD").stdout.strip()
        pushed = git("push", str(remote), "HEAD:refs/heads/main")
        self.assertEqual(pushed.returncode, 0, pushed.stderr)
        skill = self.homes["codex"] / "skills/unrecorded"
        skill.mkdir()
        (skill / "SKILL.md").write_text("new local skill")
        self.assertEqual(git("commit", "--allow-empty", "-qm", "next").returncode, 0)
        blocked = git("push", str(remote), "HEAD:refs/heads/main")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("codex: skill unrecorded is not recorded", blocked.stderr)
        tip = subprocess.check_output(["git", "--git-dir", str(remote), "rev-parse", "main"], text=True)
        self.assertEqual(tip.strip(), first)

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from portable import sync


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "skills/shared").mkdir(parents=True)
        (self.repo / "skills/shared/SKILL.md").write_text("shared skill")
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

    def test_local_edit_to_managed_skill_is_reported(self):
        (self.homes["codex"] / "skills/shared/SKILL.md").write_text("local edit")
        self.assertEqual(self.check(), [
            "codex: skill shared differs from skills/shared; copy the intended edits into the repository"
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

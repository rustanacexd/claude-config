import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from portable.manage import refresh
from portable.links import link_codex_config
from portable import apps
from native_command import argv_for

SOURCE = Path(__file__).resolve().parents[1]


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="portable test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "codex").mkdir()
        (self.repo / "skills/example/references").mkdir(parents=True)
        (self.repo / "skills/example/SKILL.md").write_text("skill")
        (self.repo / "skills/example/references/detail.md").write_text("nested")
        (self.repo / "AGENTS.md").write_text("instructions")
        (self.repo / "portable.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "assets": [
                        {
                            "source": "AGENTS.md",
                            "destination": "AGENTS.md",
                            "apps": ["codex"],
                        },
                        {
                            "source": "skills/example",
                            "destination": "skills/example",
                            "apps": ["codex", "claude"],
                        },
                    ],
                }
            )
        )
        (self.repo / "plugins.json").write_text('{"schema":1,"plugins":[]}')
        (self.repo / "settings.json").write_text('{"model":"shared","feature":true}')
        self.template('model="shared"\n[features]\nhooks=true\n')
        self.home = self.root / "home with spaces"
        self.home.mkdir()

    def template(self, text):
        (self.repo / "codex/config.template.toml").write_text(text)

    def run_refresh(self):
        return refresh(self.repo, {"codex": self.home}, ["codex"])

    def config(self):
        return tomllib.loads((self.home / "config.toml").read_text())

    def backups(self):
        return sorted((self.home / ".claude-config/backups").rglob("*"))

    def require_symlinks(self):
        probe = self.root / "link-probe"
        try:
            probe.symlink_to(self.repo)
        except OSError:
            self.skipTest("Runner cannot create symlink fixture")
        finally:
            probe.unlink(missing_ok=True)

    def test_opt_in_config_link_preserves_live_bytes_and_refreshes(self):
        self.require_symlinks()
        self.run_refresh()
        path = self.home / "config.toml"
        live = path.read_bytes() + b'\nservice_note = "local"\n'
        path.write_bytes(live)
        target = self.repo / "codex/config.toml"
        target.write_text('model="stale checkout copy"\n')
        link_codex_config(self.repo, self.home)
        self.assertTrue(path.is_symlink())
        self.assertEqual(path.resolve(), target.resolve())
        self.assertEqual(target.read_bytes(), live)
        self.assertTrue(any(p.name == "checkout-config.toml" for p in self.backups()))
        before = target.stat().st_mtime_ns
        self.assertEqual(self.run_refresh()[0], [])
        link_codex_config(self.repo, self.home)
        self.assertEqual(target.stat().st_mtime_ns, before)
        self.template('model="updated"\n[features]\nhooks=true\n')
        self.run_refresh()
        self.assertTrue(path.is_symlink())
        self.assertEqual(self.config()["model"], "updated")
        self.assertIn(b'service_note', target.read_bytes())

    def test_new_config_link_does_not_import_an_unrelated_legacy_baseline(self):
        self.require_symlinks()
        legacy = 'model="local"\n[marketplaces.keep]\nsource="keep-local-plugin-source"\n'
        (self.repo / "codex/.template.snapshot.toml").write_text(legacy)
        (self.home / "config.toml").write_text(legacy)
        link_codex_config(self.repo, self.home)
        self.run_refresh()
        self.assertTrue((self.home / "config.toml").is_symlink())
        self.assertEqual(self.config()["marketplaces"]["keep"]["source"], "keep-local-plugin-source")

    def test_config_link_rejects_retargeting_without_writing_foreign_file(self):
        self.require_symlinks()
        self.run_refresh()
        target = link_codex_config(self.repo, self.home)
        foreign = self.root / "foreign.toml"
        foreign.write_text('model="foreign"\n')
        path = self.home / "config.toml"
        path.unlink()
        path.symlink_to(foreign)
        with self.assertRaisesRegex(ValueError, "config link changed"):
            self.run_refresh()
        self.assertEqual(foreign.read_text(), 'model="foreign"\n')
        self.assertEqual(tomllib.loads(target.read_text())["model"], "shared")

    def test_config_link_can_be_restored_after_app_replaces_link(self):
        self.require_symlinks()
        self.run_refresh()
        target = link_codex_config(self.repo, self.home)
        path = self.home / "config.toml"
        path.unlink()
        path.write_text('model="app edit"\n')
        link_codex_config(self.repo, self.home)
        self.assertTrue(path.is_symlink())
        self.assertEqual(target.read_text(), 'model="app edit"\n')

    def test_real_cli_config_link(self):
        self.require_symlinks()
        source = self.root / "link CLI source"
        shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        command = [sys.executable, str(source / "manage.py")]
        home = self.root / "link CLI home"
        for operation in ("refresh", "link", "refresh"):
            result = subprocess.run(
                command + [operation, "--app", "codex", "--home", str(home)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((home / "config.toml").is_symlink())
        self.assertEqual((home / "config.toml").resolve(), (source / "codex/config.toml").resolve())

    def test_real_cli_legacy_directory_links(self):
        source = self.root / "CLI source"
        shutil.copytree(
            SOURCE, source, ignore=shutil.ignore_patterns(".git", "__pycache__")
        )
        home = self.root / "legacy CLI"
        snapshots = {
            p: (p.read_bytes(), p.stat().st_mtime_ns)
            for p in (source / "skills/show-me").rglob("*")
            if p.is_file()
        }
        for app in ("claude", "codex"):
            root = home / app / "skills"
            root.mkdir(parents=True)
            target = source / "skills/show-me"
            (root / "show-me").symlink_to(
                target if app == "claude" else os.path.relpath(target, root.resolve()),
                target_is_directory=True,
            )
        result = subprocess.run(
            [sys.executable, str(source / "manage.py"), "refresh", "--home", str(home)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for app in ("claude", "codex"):
            self.assertFalse((home / app / "skills/show-me").is_symlink())
            self.assertEqual(
                (home / app / "skills/show-me/SKILL.md").read_bytes(),
                (source / "skills/show-me/SKILL.md").read_bytes(),
            )
        self.assertEqual(
            snapshots, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshots}
        )
        result = subprocess.run(
            [sys.executable, str(source / "manage.py"), "refresh", "--home", str(home)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout, "Applied 0 file changes\n")

    def legacy_root(self, home=None, destination="skills/example"):
        home = self.home if home is None else home
        path = home / destination
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(self.repo / "skills/example", target_is_directory=True)
        return path

    def test_directory_link_remapped_nested_empty_and_foreign(self):
        (self.repo / "skills/example/empty/deeper").mkdir(parents=True)
        manifest = json.loads((self.repo / "portable.json").read_text())
        manifest["assets"][1]["destination"] = "remapped/skill"
        (self.repo / "portable.json").write_text(json.dumps(manifest))
        root = self.legacy_root(destination="remapped/skill")
        self.run_refresh()
        self.assertFalse(root.is_symlink())
        self.assertTrue((root / "empty/deeper").is_dir())
        self.assertEqual((root / "references/detail.md").read_text(), "nested")
        self.assertEqual(self.run_refresh()[0], [])
        shutil.rmtree(root)
        foreign = self.root / "foreign"
        foreign.mkdir()
        root.symlink_to(foreign, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Foreign"):
            self.run_refresh()
        self.assertTrue(root.is_symlink())

    def test_remapped_child_file_link_uses_manifest_source(self):
        manifest = json.loads((self.repo / "portable.json").read_text())
        manifest["assets"][1]["destination"] = "remapped/skill"
        (self.repo / "portable.json").write_text(json.dumps(manifest))
        root = self.home / "remapped/skill"
        root.mkdir(parents=True)
        (root / "SKILL.md").symlink_to(self.repo / "skills/example/SKILL.md")
        self.run_refresh()
        self.assertFalse((root / "SKILL.md").is_symlink())
        self.assertEqual((root / "SKILL.md").read_text(), "skill")

    def test_invalid_second_app_journal_payload_no_first_app_write(self):
        root = self.legacy_root()
        other = self.root / "claude"
        state = other / ".claude-config"
        state.mkdir(parents=True)
        transaction = {
            "schema": 1,
            "baseline": {"schema": 1, "files": {}, "config": {}},
            "roots": [None],
            "updates": [],
        }
        (state / "journal.json").write_text(json.dumps(transaction))
        with self.assertRaises(ValueError):
            refresh(
                self.repo, {"codex": self.home, "claude": other}, ["codex", "claude"]
            )
        self.assertTrue(root.is_symlink())
        self.assertFalse((self.home / ".claude-config").exists())

    @unittest.skipUnless(os.name == "nt", "Windows directory junction")
    def test_windows_junction_is_rejected_without_target_write(self):
        root = self.home / "skills/example"
        root.parent.mkdir(parents=True)
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(root), str(self.repo / "skills/example")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        before = (self.repo / "skills/example/SKILL.md").read_bytes()
        with self.assertRaisesRegex(ValueError, "Foreign"):
            self.run_refresh()
        self.assertEqual((self.repo / "skills/example/SKILL.md").read_bytes(), before)
        root.rmdir()

    def test_directory_link_unsafe_ancestors_and_broken_roots(self):
        for kind in ("ancestor", "broken"):
            with self.subTest(kind=kind):
                home = self.root / kind
                home.mkdir()
                if kind == "ancestor":
                    (home / "skills").symlink_to(self.repo / "skills", target_is_directory=True)
                elif kind == "broken":
                    (home / "skills").mkdir()
                    (home / "skills/example").symlink_to(self.root / "missing", target_is_directory=True)
                with self.assertRaises(ValueError):
                    refresh(self.repo, {"codex": home}, ["codex"])
                self.assertFalse((home / ".claude-config").exists())

    def test_directory_link_empty_asset(self):
        shutil.rmtree(self.repo / "skills/example")
        (self.repo / "skills/example").mkdir()
        root = self.legacy_root()
        self.run_refresh()
        self.assertTrue(root.is_dir())
        self.assertFalse(root.is_symlink())
        self.assertEqual(self.run_refresh()[0], [])

    def test_fresh_machine_and_identical_rerun(self):
        self.run_refresh()
        self.assertEqual(self.config()["model"], "shared")
        self.assertFalse((self.home / "config.toml").is_symlink())
        self.assertEqual(
            (self.home / "skills/example/references/detail.md").read_text(), "nested"
        )
        times = {
            p: p.stat().st_mtime_ns
            for p in self.home.rglob("*")
            if p.is_file() and p.name != "lock"
        }
        changed, _ = self.run_refresh()
        self.assertEqual(changed, [])
        self.assertEqual(times, {p: p.stat().st_mtime_ns for p in times})
        self.assertEqual(self.backups(), [])

    def test_shared_defaults_update_remove_and_local_changes(self):
        self.run_refresh()
        self.template('model="new"\nother=1\n')
        self.run_refresh()
        self.assertEqual(self.config()["model"], "new")
        self.assertEqual(self.config()["other"], 1)
        (self.home / "config.toml").write_text('model="local"\n')
        self.template('model="newer"\nother=2\nadded=3\n')
        self.run_refresh()
        self.assertEqual(self.config()["model"], "local")
        self.assertNotIn("other", self.config())
        self.assertEqual(self.config()["added"], 3)

    def test_entire_table_deletion_and_array_override(self):
        self.template("items=[1,2]\n[features]\nhooks=true\n")
        self.run_refresh()
        (self.home / "config.toml").write_text("items=[9]\n")
        self.template("items=[1,2,3]\n[features]\nhooks=false\nnew=true\n")
        self.run_refresh()
        self.assertEqual(self.config()["items"], [9])
        self.assertNotIn("features", self.config())

    def test_removed_shared_table_keeps_unknown_local_keys(self):
        self.run_refresh()
        (self.home / "config.toml").write_text(
            'model="shared"\n[features]\nhooks=true\nlocal=7\n'
        )
        self.template('model="shared"\n')
        self.run_refresh()
        self.assertEqual(self.config()["features"], {"local": 7})

    def test_edited_removed_deleted_and_unmanaged_skills(self):
        self.run_refresh()
        skill = self.home / "skills/example"
        (skill / "references/detail.md").write_text("local edit")
        (skill / "unmanaged.md").write_text("unmanaged")
        (skill / "SKILL.md").unlink()
        (self.repo / "skills/example/references/detail.md").unlink()
        self.run_refresh()
        self.assertEqual((skill / "references/detail.md").read_text(), "local edit")
        self.assertEqual((skill / "unmanaged.md").read_text(), "unmanaged")
        self.assertFalse((skill / "SKILL.md").exists())

    def test_foreign_symlinks_migrate_without_target_write(self):
        foreign = self.root / "foreign.toml"
        foreign.write_text('model="foreign"\n')
        target = self.root / "foreign.md"
        target.write_text("foreign")
        try:
            (self.home / "config.toml").symlink_to(foreign)
            (self.home / "AGENTS.md").symlink_to(target)
        except OSError:
            self.skipTest("Runner cannot create symlink fixture")
        self.run_refresh()
        self.assertEqual(foreign.read_text(), 'model="foreign"\n')
        self.assertEqual(target.read_text(), "foreign")
        self.assertFalse((self.home / "config.toml").is_symlink())
        self.assertFalse((self.home / "AGENTS.md").is_symlink())
        self.assertEqual((self.home / "AGENTS.md").read_text(), "foreign")
        self.assertTrue(any(p.name.endswith(".symlink.json") for p in self.backups()))

    def test_malformed_inputs_no_mutation(self):
        (self.home / "config.toml").write_text("invalid=")
        before = set(self.home.rglob("*"))
        with self.assertRaises(ValueError):
            self.run_refresh()
        self.assertEqual(before, set(self.home.rglob("*")))

    def test_malformed_second_app_no_first_app_mutation(self):
        other = self.root / "claude"
        other.mkdir()
        (other / "settings.json").write_text("invalid")
        with self.assertRaises(ValueError):
            refresh(
                self.repo, {"codex": self.home, "claude": other}, ["codex", "claude"]
            )
        self.assertFalse((self.home / "config.toml").exists())

    def test_cross_home_state_separation_and_source_unchanged(self):
        before = {
            p.relative_to(self.repo): p.read_bytes()
            for p in self.repo.rglob("*")
            if p.is_file()
        }
        self.run_refresh()
        other = self.root / "other"
        refresh(self.repo, {"codex": other}, ["codex"])
        (self.home / "config.toml").write_text('model="local"\n')
        self.run_refresh()
        self.assertEqual(
            tomllib.loads((other / "config.toml").read_text())["model"], "shared"
        )
        self.assertEqual(
            before,
            {
                p.relative_to(self.repo): p.read_bytes()
                for p in self.repo.rglob("*")
                if p.is_file()
            },
        )

    def test_legacy_journal_refused(self):
        (self.repo / "codex/.refresh.journal.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Legacy"):
            self.run_refresh()
        self.assertFalse((self.home / "config.toml").exists())

    def test_claude_auth_local_changes_retained(self):
        (self.home / "settings.json").write_text(
            '{"env":{"ANTHROPIC_AUTH_TOKEN":"canary-secret"},"model":"local"}'
        )
        refresh(self.repo, {"claude": self.home}, ["claude"])
        d = json.loads((self.home / "settings.json").read_text())
        self.assertEqual(d["env"]["ANTHROPIC_AUTH_TOKEN"], "canary-secret")
        self.assertEqual(d["model"], "local")
        self.assertNotIn("canary-secret", (self.repo / "settings.json").read_text())

    def test_shared_secret_is_rejected_before_home_mutation(self):
        (self.repo / "settings.json").write_text(
            '{"env":{"ANTHROPIC_AUTH_TOKEN":"canary-secret"}}'
        )
        with self.assertRaisesRegex(ValueError, "machine authentication"):
            refresh(self.repo, {"claude": self.home}, ["claude"])
        self.assertEqual(list(self.home.iterdir()), [])

    def test_removed_owned_skill_migration_preserves_edits_and_external_files(self):
        homes = {app: self.root / app for app in ("claude", "codex")}
        refresh(self.repo, homes, list(homes))
        for home in homes.values():
            skill = home / "skills/example"
            (skill / "references/detail.md").write_text("local edit")
            (skill / "external.md").write_text("upstream installer file")
            external = home / "skills/external/SKILL.md"
            external.parent.mkdir(parents=True)
            external.write_text("installed by npx skills")
        manifest_path = self.repo / "portable.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["assets"] = [
            asset for asset in manifest["assets"]
            if not asset["source"].startswith("skills/")
        ]
        manifest_path.write_text(json.dumps(manifest))
        _, issues = refresh(self.repo, homes, list(homes))
        for home in homes.values():
            skill = home / "skills/example"
            self.assertFalse((skill / "SKILL.md").exists())
            self.assertEqual((skill / "references/detail.md").read_text(), "local edit")
            self.assertEqual((skill / "external.md").read_text(), "upstream installer file")
            self.assertEqual(
                (home / "skills/external/SKILL.md").read_text(), "installed by npx skills"
            )
            (skill / "references/detail.md").write_text("nested")
            (skill / "SKILL.md").write_text("skill")
        self.assertTrue(
            any("edited removed asset retained" in issue for issue in issues)
        )
        changed, _ = refresh(self.repo, homes, list(homes))
        self.assertEqual(changed, [])
        for home in homes.values():
            self.assertEqual((home / "skills/example/references/detail.md").read_text(), "nested")
            self.assertEqual((home / "skills/example/SKILL.md").read_text(), "skill")

    def test_local_profile_retains_secret_outside_repo(self):
        (self.home / "portable.local.json").write_text(
            '{"env":{"ANTHROPIC_AUTH_TOKEN":"canary-secret"}}'
        )
        refresh(self.repo, {"claude": self.home}, ["claude"])
        self.assertEqual(
            json.loads((self.home / "settings.json").read_text())["env"][
                "ANTHROPIC_AUTH_TOKEN"
            ],
            "canary-secret",
        )
        self.assertNotIn("canary-secret", (self.repo / "settings.json").read_text())

    def test_path_collision_and_escape_rejected(self):
        for path in ("../escape", "C:/escape", "CON", "trailing."):
            d = {
                "schema": 1,
                "assets": [
                    {"source": "AGENTS.md", "destination": path, "apps": ["codex"]}
                ],
            }
            (self.repo / "portable.json").write_text(json.dumps(d))
            with self.assertRaises(ValueError):
                self.run_refresh()
        self.assertFalse((self.home / "config.toml").exists())

    def test_pstack_models_upgrade_preserves_local_edits(self):
        repo = self.root / "upgrade repo"
        shutil.copytree(SOURCE, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        manifest = json.loads((repo / "portable.json").read_text())
        old_manifest = dict(manifest)
        old_manifest["assets"] = [
            asset for asset in manifest["assets"]
            if asset["destination"] != "pstack-models.md"
        ] + [{"source": "pstack-models.md", "destination": "pstack-models.md",
              "apps": ["claude", "codex"]}]
        old_sheet = (SOURCE / "codex/pstack-models.md").read_bytes()
        for edited in (False, True):
            with self.subTest(edited=edited):
                homes = {app: self.root / str(edited) / app
                         for app in ("claude", "codex")}
                (repo / "portable.json").write_text(json.dumps(old_manifest))
                (repo / "pstack-models.md").write_bytes(old_sheet)
                refresh(repo, homes, list(homes))
                local = old_sheet + b"\nfeature, refactoring: local-model\n"
                if edited:
                    for home in homes.values():
                        (home / "pstack-models.md").write_bytes(local)
                (repo / "portable.json").write_text(json.dumps(manifest))
                (repo / "pstack-models.md").write_bytes(
                    (SOURCE / "pstack-models.md").read_bytes()
                )
                refresh(repo, homes, list(homes))
                for app, home in homes.items():
                    expected = local if edited else (
                        SOURCE / ("pstack-models.md" if app == "claude"
                                  else "codex/pstack-models.md")
                    ).read_bytes()
                    self.assertEqual((home / "pstack-models.md").read_bytes(), expected)
                changed, _ = refresh(repo, homes, list(homes))
                self.assertEqual(changed, [])

    def test_real_cli_fresh_home_and_canary_output(self):
        home = self.root / "CLI home"
        env = dict(os.environ, ANTHROPIC_AUTH_TOKEN="secret-canary")
        result = subprocess.run(
            [sys.executable, str(SOURCE / "manage.py"), "refresh", "--home", str(home)],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("secret-canary", result.stdout + result.stderr)
        rerun = subprocess.run(
            [sys.executable, str(SOURCE / "manage.py"), "refresh", "--home", str(home)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(rerun.stdout, "Applied 0 file changes\n")


@unittest.skipUnless(os.name == "nt", "Windows PowerShell launcher")
class WindowsLauncherTests(unittest.TestCase):
    def test_npm_claude_native_entry_needs_no_node(self):
        with tempfile.TemporaryDirectory(
            prefix="native Claude with spaces "
        ) as directory:
            root = Path(directory)
            executable = root / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"fixture")
            shim = root / "claude.cmd"
            arguments = ["mcp", "get", "sentry"]
            with patch.object(
                shutil,
                "which",
                side_effect=lambda name: str(shim) if name == "claude" else None,
            ):
                self.assertEqual(
                    argv_for("claude", arguments), [str(executable), *arguments]
                )

    def test_native_cmd_shim_and_scoped_longpaths(self):
        with tempfile.TemporaryDirectory(
            prefix="native shim with spaces "
        ) as directory:
            root = Path(directory)
            script = root / "node_modules/@openai/codex/bin/codex.js"
            script.parent.mkdir(parents=True)
            script.write_text(
                "import json, os, sys\n"
                "print(json.dumps({'args': sys.argv[1:], 'count': os.environ['GIT_CONFIG_COUNT'], "
                "'original': os.environ['GIT_CONFIG_VALUE_0'], 'key': os.environ['GIT_CONFIG_KEY_1'], "
                "'value': os.environ['GIT_CONFIG_VALUE_1']}))\n"
            )
            shim = root / "codex.cmd"
            shim.write_text("@exit /b 99\n")
            arguments = [
                "mcp",
                "add-json",
                json.dumps({"command": 'path with spaces & ^ %PATH% ! "quotes"'}),
            ]
            with (
                patch.object(
                    apps.shutil,
                    "which",
                    side_effect=lambda name: (
                        sys.executable if name == "node" else str(shim)
                    ),
                ),
                patch.dict(
                    os.environ,
                    GIT_CONFIG_COUNT="1",
                    GIT_CONFIG_KEY_0="example.original",
                    GIT_CONFIG_VALUE_0="retained",
                ),
            ):
                result = apps.command("codex", arguments, root)
                self.assertEqual(os.environ["GIT_CONFIG_COUNT"], "1")
            self.assertEqual(result["args"], arguments)
            self.assertEqual(result["count"], "2")
            self.assertEqual(result["original"], "retained")
            self.assertEqual(
                (result["key"], result["value"]), ("core.longpaths", "true")
            )

    def test_missing_launcher_and_child_exit_code(self):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell is None:
            self.skipTest("PowerShell unavailable")
        with tempfile.TemporaryDirectory(prefix="launcher with spaces ") as directory:
            root = Path(directory)
            env = dict(os.environ, PATH=str(root))
            argv = [
                shell,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(SOURCE / "refresh.ps1"),
            ]
            missing = subprocess.run(argv, env=env, capture_output=True, text=True)
            self.assertEqual(missing.returncode, 1, missing.stderr)
            for name in ("python.cmd", "py.cmd"):
                (root / name).write_text("@exit /b 7\n")
                result = subprocess.run(argv, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 7, result.stderr)


class NativeTests(unittest.TestCase):
    def test_default_claude_home_retains_native_config_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environments = []

            def run(argv, **kwargs):
                environments.append(kwargs["env"])
                return subprocess.CompletedProcess(argv, 0, "[]", "")

            with (
                patch.object(Path, "home", return_value=root),
                patch.dict(os.environ, {}, clear=True),
                patch.object(apps.shutil, "which", return_value="claude.exe"),
                patch.object(apps.subprocess, "run", run),
            ):
                apps.command("claude", ["plugin", "list", "--json"], root / ".claude")
                self.assertNotIn("CLAUDE_CONFIG_DIR", environments[-1])
                apps.command("claude", ["plugin", "list", "--json"], root / "custom")
                self.assertEqual(
                    environments[-1]["CLAUDE_CONFIG_DIR"], str(root / "custom")
                )
                os.environ["CLAUDE_CONFIG_DIR"] = str(root / ".claude")
                apps.command("claude", ["plugin", "list", "--json"], root / ".claude")
                self.assertEqual(
                    environments[-1]["CLAUDE_CONFIG_DIR"], str(root / ".claude")
                )

    def test_failed_native_command_redacts_output(self):
        result = subprocess.CompletedProcess([], 1, "canary-secret", "canary-secret")
        with (
            patch.object(apps.shutil, "which", return_value="claude"),
            patch.object(apps.subprocess, "run", return_value=result),
        ):
            with self.assertRaises(ValueError) as error:
                apps.command("claude", ["plugin", "list", "--json"], Path("/unused"))
        self.assertNotIn("canary-secret", str(error.exception))


if __name__ == "__main__":
    unittest.main()

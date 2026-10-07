import json
import io
from contextlib import redirect_stdout, redirect_stderr
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from portable.config import equal, render, parse
from portable.manage import refresh, load, plan, parse as parse_config
from portable import install, apps
from native_command import argv_for
import manage

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

    def test_fresh_machine_and_identical_rerun(self):
        with patch.object(Path, "symlink_to", side_effect=OSError("no privilege")):
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

    def test_existing_bytes_and_local_instruction_preserved(self):
        self.template('model="shared"\n')
        live = b'# formatting\nmodel="local"\n'
        (self.home / "config.toml").write_bytes(live)
        (self.home / "AGENTS.md").write_text("local")
        self.run_refresh()
        original = (self.home / "config.toml").read_bytes()
        self.run_refresh()
        self.assertEqual((self.home / "config.toml").read_bytes(), original)
        self.assertEqual((self.home / "AGENTS.md").read_text(), "local")

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

    def test_removed_unchanged_owned_file_deleted(self):
        self.run_refresh()
        (self.repo / "skills/example/references/detail.md").unlink()
        self.run_refresh()
        self.assertFalse((self.home / "skills/example/references/detail.md").exists())

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

    def test_crash_recovery_all_durable_boundaries(self):
        for name in ("journal.json", "AGENTS.md", "config.toml", "baseline.json"):
            with self.subTest(name=name):
                home = self.root / name
                home.mkdir()
                atomic = install.atomic
                triggered = False

                def interrupted(path, data):
                    nonlocal triggered
                    atomic(path, data)
                    if path.name == name and not triggered:
                        triggered = True
                        raise RuntimeError("crash")

                with patch.object(install, "atomic", interrupted):
                    with self.assertRaises(RuntimeError):
                        refresh(self.repo, {"codex": home}, ["codex"])
                backups = sorted((home / ".claude-config/backups").rglob("*"))
                refresh(self.repo, {"codex": home}, ["codex"])
                self.assertEqual(
                    tomllib.loads((home / "config.toml").read_text())["model"], "shared"
                )
                self.assertFalse((home / ".claude-config/journal.json").exists())
                self.assertEqual(
                    backups, sorted((home / ".claude-config/backups").rglob("*"))
                )

    def test_crash_then_app_edit_refuses_overwrite(self):
        atomic = install.atomic

        def interrupted(path, data):
            atomic(path, data)
            if path.name == "journal.json":
                raise RuntimeError("crash")

        with patch.object(install, "atomic", interrupted):
            with self.assertRaises(RuntimeError):
                self.run_refresh()
        (self.home / "config.toml").write_text('model="app"\n')
        with self.assertRaisesRegex(ValueError, "interrupted"):
            self.run_refresh()
        self.assertEqual((self.home / "config.toml").read_text(), 'model="app"\n')
        self.assertTrue((self.home / ".claude-config/journal.json").exists())

    def test_app_edit_between_plan_and_publish_refuses(self):
        manifest, plugins = load(self.repo)
        with install.locked(self.home) as state:
            updates, baseline, _ = plan(
                self.repo, manifest, plugins, "codex", self.home, state
            )
            (self.home / "config.toml").write_text('model="app"\n')
            with self.assertRaisesRegex(ValueError, "before publication"):
                install.publish(self.home, state, updates, baseline)
        self.assertFalse((self.home / ".claude-config/journal.json").exists())

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
        self.run_refresh()
        skill = self.home / "skills/example"
        (skill / "references/detail.md").write_text("local edit")
        (skill / "external.md").write_text("upstream installer file")
        external = self.home / "skills/external/SKILL.md"
        external.parent.mkdir(parents=True)
        external.write_text("installed by npx skills")
        manifest_path = self.repo / "portable.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["assets"] = [
            asset for asset in manifest["assets"]
            if not asset["source"].startswith("skills/")
        ]
        manifest_path.write_text(json.dumps(manifest))
        _, issues = self.run_refresh()
        self.assertFalse((skill / "SKILL.md").exists())
        self.assertEqual((skill / "references/detail.md").read_text(), "local edit")
        self.assertEqual((skill / "external.md").read_text(), "upstream installer file")
        self.assertEqual(external.read_text(), "installed by npx skills")
        self.assertTrue(
            any("edited removed asset retained" in issue for issue in issues)
        )
        changed, _ = self.run_refresh()
        self.assertEqual(changed, [])

    def test_repository_only_manages_authored_skills_and_install_guide(self):
        manifest, _ = load(SOURCE)
        skills = [
            asset["source"] for asset in manifest["assets"]
            if asset["source"].startswith("skills/")
        ]
        self.assertEqual(
            sorted(skills), ["skills/explain-diff-html", "skills/show-me"]
        )
        self.assertFalse((SOURCE / "skills/vendor").exists())
        homes = {app: self.root / app for app in ("claude", "codex")}
        refresh(SOURCE, homes, list(homes))
        for home in homes.values():
            self.assertEqual(
                (home / "SKILLS.md").read_bytes(), (SOURCE / "SKILLS.md").read_bytes()
            )
            self.assertEqual(
                sorted(path.name for path in (home / "skills").iterdir()),
                ["explain-diff-html", "show-me"],
            )
        changed, _ = refresh(SOURCE, homes, list(homes))
        self.assertEqual(changed, [])

    def test_inventory_routes_third_party_skills_to_upstream_guide(self):
        output = io.StringIO()
        with patch.object(manage, "REPO", self.repo), patch.object(
            manage, "installed", return_value={}
        ), patch.object(sys, "argv", ["manage.py", "inventory", "--app", "codex",
                                      "--home", str(self.home)]), redirect_stdout(
            output
        ), redirect_stderr(io.StringIO()):
            manage.main()
        self.assertIn("follow SKILLS.md with npx skills", output.getvalue())
        self.assertIn("does not install or verify them", output.getvalue())

    def test_repository_manifest_and_sentry_environment(self):
        load(SOURCE)
        self.run_refresh()
        allowed = self.config()["mcp_servers"]["sentry"]["env_vars"]
        for name in ("SENTRY_ACCESS_TOKEN", "APPDATA", "LOCALAPPDATA", "USERPROFILE"):
            self.assertIn(name, allowed)

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

    def test_native_install_retains_local_disabled_flag(self):
        plugin = {
            "app": "claude",
            "id": "x@y",
            "enabled": True,
            "kind": "native",
            "source": "https://github.com/x/y.git",
            "marketplace": "y",
        }
        (self.repo / "plugins.json").write_text(
            json.dumps({"schema": 1, "plugins": [plugin]})
        )
        (self.home / "settings.json").write_text('{"enabledPlugins":{"x@y":false}}')
        refresh(self.repo, {"claude": self.home}, ["claude"])

        def flip(app, home, plugins):
            self.assertFalse(plugins[0]["enabled"])
            path = home / "settings.json"
            config = json.loads(path.read_text())
            config["enabledPlugins"]["x@y"] = True
            path.write_text(json.dumps(config))
            return []

        with (
            patch.object(apps, "restore", flip),
            patch.object(apps, "installed", return_value={}),
        ):
            apps.restore_preserving_flags("claude", self.home, [plugin])
        self.assertFalse(
            json.loads((self.home / "settings.json").read_text())["enabledPlugins"][
                "x@y"
            ]
        )
        refresh(self.repo, {"claude": self.home}, ["claude"])
        self.assertFalse(
            json.loads((self.home / "settings.json").read_text())["enabledPlugins"][
                "x@y"
            ]
        )

    def test_journal_escape_and_reparse_parent_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            install.safe_path(self.home, "../escape")
        with patch.object(install, "linked", return_value=True):
            with self.assertRaisesRegex(ValueError, "symlink parent"):
                install.safe_path(self.home, "skills/example/file")

    def test_native_install_retains_deleted_plugin_table(self):
        for app, section, filename in (
            ("claude", "enabledPlugins", "settings.json"),
            ("codex", "plugins", "config.toml"),
        ):
            with self.subTest(app=app):
                home = self.root / app
                plugin = {
                    "app": app,
                    "id": "x@y",
                    "enabled": True,
                    "kind": "native",
                    "source": "https://github.com/x/y.git",
                    "marketplace": "y",
                }
                (self.repo / "plugins.json").write_text(
                    json.dumps({"schema": 1, "plugins": [plugin]})
                )
                refresh(self.repo, {app: home}, [app])
                path = home / filename
                config = parse_config(app, path.read_bytes())
                config.pop(section)
                path.write_bytes(
                    json.dumps(config).encode() if app == "claude" else render(config)
                )

                def native_install(app, home, plugins):
                    changed = dict(config)
                    changed[section] = {
                        "x@y": True if app == "claude" else {"enabled": True}
                    }
                    path.write_bytes(
                        json.dumps(changed).encode()
                        if app == "claude"
                        else render(changed)
                    )
                    return []

                with (
                    patch.object(apps, "restore", native_install),
                    patch.object(apps, "installed", return_value={}),
                ):
                    apps.restore_preserving_flags(app, home, [plugin])
                refresh(self.repo, {app: home}, [app])
                result = parse_config(app, path.read_bytes())
                self.assertNotIn(section, result)

    def test_serializer_complete_types(self):
        data = tomllib.loads(
            '"quoted.key"="Unicode 😀 and \\u007f"\nfloat=nan\ninfinity=-inf\nwhen=1979-05-27T07:32:00Z\nlocal=1979-05-27T07:32:00\ndate=1979-05-27\ntime=07:32:00\nrecords=[{path="x",enabled=true},{path="y",numbers=[1,2.5]}]\n[empty]\n'
        )
        self.assertTrue(equal(parse(render(data)), data))

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

    def test_real_repository_app_specific_pstack_models(self):
        homes = {app: self.root / app for app in ("claude", "codex")}
        refresh(SOURCE, homes, list(homes))
        claude = (homes["claude"] / "pstack-models.md").read_bytes()
        codex = (homes["codex"] / "pstack-models.md").read_bytes()
        self.assertIn(b"feature, refactoring: opus", claude.splitlines())
        self.assertIn(b"strongest judgment: fable", claude.splitlines())
        self.assertIn(b"feature, refactoring: gpt-6.1-sol", codex.splitlines())
        self.assertEqual(claude, (SOURCE / "pstack-models.md").read_bytes())
        self.assertEqual(codex, (SOURCE / "codex/pstack-models.md").read_bytes())
        self.assertNotEqual(claude, codex)
        changed, _ = refresh(SOURCE, homes, list(homes))
        self.assertEqual(changed, [])

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

    def test_failed_plugin_does_not_skip_later_restores(self):
        plugins = [
            {
                "id": f"{name}@market",
                "app": "claude",
                "marketplace": "market",
                "source": "https://github.com/test/market.git",
                "kind": "native",
                "enabled": True,
            }
            for name in ("broken", "working")
        ]
        found = []

        def command(app, arguments, home, **kwargs):
            if arguments[:3] == ["plugin", "list", "--json"]:
                return found
            if arguments[:3] == ["plugin", "marketplace", "list"]:
                return [{"name": "market"}]
            if arguments[1] == "install":
                if arguments[2] == "broken@market":
                    raise ValueError("native installation failed")
                found.append({"id": arguments[2], "enabled": True})

        with patch.object(apps, "command", command):
            issues = apps.restore("claude", Path("unused"), plugins)
        self.assertEqual([p["id"] for p in found], ["working@market"])
        self.assertEqual(len(issues), 1)
        self.assertIn("broken@market", issues[0])

    def test_shapes_disabled_installs_and_idempotency(self):
        plugin = {
            "id": "example@market",
            "app": "claude",
            "marketplace": "market",
            "source": "https://github.com/test/market.git",
            "kind": "native",
            "enabled": False,
        }
        found = {}
        calls = []

        def native(app, args, home, parse_json=True):
            calls.append(args)
            if args[1] == "list":
                return list(found.values())
            if args[1:3] == ["marketplace", "list"]:
                return []
            if args[1] == "install":
                found[plugin["id"]] = {"id": plugin["id"], "enabled": True}
            if args[1] == "disable":
                self.assertFalse(parse_json)
                found[plugin["id"]]["enabled"] = False
            return {}

        with patch.object(apps, "command", native):
            self.assertEqual(apps.restore("claude", Path("/unused"), [plugin]), [])
            self.assertEqual(apps.restore("claude", Path("/unused"), [plugin]), [])
        self.assertEqual(sum(c[1] == "install" for c in calls), 1)
        self.assertEqual(sum(c[1] == "disable" for c in calls), 1)

    def test_sentry_existing_definition_never_replaced(self):
        with patch.object(
            apps, "command", return_value="existing private command"
        ) as native:
            apps.ensure_sentry(Path("/unused"), sys.executable)
        self.assertEqual(native.call_count, 1)
        self.assertFalse(native.call_args.kwargs["parse_json"])

    def test_sentry_missing_created_then_observed(self):
        with patch.object(
            apps, "command", side_effect=[None, "Added", "Existing"]
        ) as native:
            apps.ensure_sentry(Path("/unused"), sys.executable)
        self.assertEqual(native.call_count, 3)
        self.assertEqual(native.call_args_list[1].args[1][1], "add-json")

    def test_codex_object_shape_and_missing_capability(self):
        with patch.object(
            apps,
            "command",
            return_value={"installed": [{"pluginId": "x@y", "enabled": False}]},
        ):
            self.assertIn("x@y", apps.installed("codex", Path("/unused")))
        with patch.object(apps, "command", side_effect=ValueError("CLI missing")):
            self.assertEqual(
                apps.restore("codex", Path("/unused"), []), ["CLI missing"]
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

    def test_runtime_plugins_not_restored_as_native(self):
        plugin = {"id": "x@runtime", "kind": "app-provided", "enabled": False}
        with (
            patch.object(apps, "installed", return_value={}),
            patch.object(apps, "command", return_value=[]),
        ):
            issues = apps.restore("codex", Path("/unused"), [plugin])
        self.assertTrue(any("app availability" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()

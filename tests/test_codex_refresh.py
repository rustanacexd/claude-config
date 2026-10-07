import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('codex_refresh', SOURCE / 'codex/refresh.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo/codex'
        self.repo.mkdir(parents=True)
        self.home = self.root / 'home/.codex'
        self.home.mkdir(parents=True)
        self.template('model = "shared"\n[features]\nhooks = true\n')
        (self.repo / 'AGENTS.md').write_bytes(b'Shared instructions\n')

    def template(self, text):
        (self.repo / 'config.template.toml').write_text(text)

    def run_refresh(self):
        with contextlib.redirect_stdout(io.StringIO()):
            refresh.refresh(self.repo, self.home)

    def config(self):
        return tomllib.loads((self.home / 'config.toml').read_text())

    def backup_files(self):
        return sorted((self.home / 'backups').glob('*/*'))

    def test_fresh_machine(self):
        self.run_refresh()
        self.assertEqual(self.config(), {'model': 'shared', 'features': {'hooks': True}})
        for name in ('config.toml', 'AGENTS.md'):
            self.assertEqual((self.home / name).resolve(), (self.repo / name).resolve())
        self.assertEqual((self.repo / 'config.toml').stat().st_mode & 0o777, 0o600)
        self.assertFalse(self.backup_files())

    def test_preserve_semantics_bytes_backups_and_rerun(self):
        live = b'# retain formatting\nmodel="local"\n[features]\nhooks=true\n[projects."/private/project"]\ntrust_level="trusted"\n'
        (self.home / 'config.toml').write_bytes(live)
        (self.home / 'AGENTS.md').write_bytes(b'Local instructions\n')
        self.run_refresh()
        self.assertEqual((self.repo / 'config.toml').read_bytes(), live)
        files = self.backup_files()
        self.assertEqual(len(files), 2)
        self.assertEqual(next(p for p in files if p.name == 'config.toml').read_bytes(), live)
        self.assertEqual(next(p for p in files if p.name == 'AGENTS.md').read_bytes(), b'Local instructions\n')
        for p in files:
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            self.assertEqual(p.parent.stat().st_mode & 0o777, 0o700)
        times = {p.name: p.stat().st_mtime_ns for p in (self.repo / 'config.toml', self.repo / '.template.snapshot.toml')}
        self.run_refresh()
        self.assertEqual(self.backup_files(), files)
        self.assertEqual({p.name: p.stat().st_mtime_ns for p in (self.repo / 'config.toml', self.repo / '.template.snapshot.toml')}, times)

    def test_shared_defaults_update_remove_and_local_changes(self):
        self.run_refresh()
        self.template('model="new"\nother=1\n')
        self.run_refresh()
        self.assertEqual(self.config(), {'model': 'new', 'other': 1})
        (self.home / 'config.toml').write_text('model="local"\n')
        self.template('model="newer"\nother=2\nadded=3\n')
        self.run_refresh()
        self.assertEqual(self.config(), {'model': 'local', 'added': 3})

    def test_entire_table_deletion_and_array_override(self):
        self.template('items=[1,2]\n[features]\nhooks=true\n')
        self.run_refresh()
        (self.home / 'config.toml').write_text('items=[9]\n')
        self.template('items=[1,2,3]\n[features]\nhooks=false\nnew=true\n')
        self.run_refresh()
        self.assertEqual(self.config(), {'items': [9]})

    def test_removed_shared_table_keeps_unknown_local_keys(self):
        self.run_refresh()
        (self.home / 'config.toml').write_text('model="shared"\n[features]\nhooks=true\nlocal=7\n')
        self.template('model="shared"\n')
        self.run_refresh()
        self.assertEqual(self.config(), {'model': 'shared', 'features': {'local': 7}})

    def test_app_replaces_symlink_adopt_repair(self):
        self.run_refresh()
        destination = self.home / 'config.toml'
        destination.unlink()
        destination.write_text('model="app"\n[features]\nhooks=true\n[hooks.state]\nhash="local"\n')
        original = destination.read_bytes()
        self.run_refresh()
        self.assertTrue(destination.is_symlink())
        self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(next(p for p in self.backup_files() if p.name == 'config.toml').read_bytes(), original)

    def test_foreign_symlink_content_and_metadata_backup(self):
        foreign = self.root / 'foreign.toml'
        foreign.write_text('model="foreign"\n[features]\nhooks=true\n')
        original = foreign.read_bytes()
        (self.home / 'config.toml').symlink_to(foreign)
        foreign_agents = self.root / 'foreign.md'
        foreign_agents.write_bytes(b'foreign instructions')
        (self.home / 'AGENTS.md').symlink_to(foreign_agents)
        self.run_refresh()
        self.assertEqual(foreign.read_bytes(), original)
        self.assertEqual(foreign_agents.read_bytes(), b'foreign instructions')
        names = {p.name for p in self.backup_files()}
        self.assertEqual(names, {'config.toml','config.toml.symlink.json','AGENTS.md','AGENTS.md.symlink.json'})
        self.assertEqual(self.config()['model'], 'foreign')

    def test_invalid_inputs_do_not_replace_links(self):
        for which in ('template', 'live'):
            with self.subTest(which=which):
                self.template('model="shared"\n')
                (self.home / 'config.toml').write_text('model="local"\n')
                (self.home / 'AGENTS.md').write_bytes(b'local')
                path = self.repo / 'config.template.toml' if which == 'template' else self.home / 'config.toml'
                path.write_text('invalid=')
                before = (self.home / 'config.toml').read_bytes()
                with self.assertRaises(tomllib.TOMLDecodeError):
                    self.run_refresh()
                self.assertFalse((self.home / 'config.toml').is_symlink())
                self.assertEqual((self.home / 'config.toml').read_bytes(), before)
                self.assertEqual((self.home / 'AGENTS.md').read_bytes(), b'local')
                self.assertFalse(self.backup_files())

    def test_crash_recovery_all_durable_boundaries(self):
        for phase in ('journal', 'config', 'snapshot', 'config_link', 'agents_link'):
            with self.subTest(phase=phase):
                with tempfile.TemporaryDirectory(dir=self.root) as directory:
                    repo, home = Path(directory)/'codex', Path(directory)/'home'
                    repo.mkdir(); home.mkdir()
                    (repo/'config.template.toml').write_text('model="shared"\n')
                    (repo/'AGENTS.md').write_text('shared instructions')
                    (home/'config.toml').write_text('model="local"\n')
                    (home/'AGENTS.md').write_text('local instructions')
                    atomic, install = refresh.atomic, refresh.install_link
                    def interrupted_atomic(path, data):
                        atomic(path, data)
                        if path.parent == repo.resolve() and path.name == {'journal': '.refresh.journal.json', 'config': 'config.toml', 'snapshot': '.template.snapshot.toml'}.get(phase):
                            raise RuntimeError('simulated crash')
                    def interrupted_link(path, target):
                        install(path, target)
                        if path.name == {'config_link': 'config.toml', 'agents_link': 'AGENTS.md'}.get(phase):
                            raise RuntimeError('simulated crash')
                    with patch.object(refresh, 'atomic', interrupted_atomic), patch.object(refresh, 'install_link', interrupted_link):
                        with self.assertRaises(RuntimeError), contextlib.redirect_stdout(io.StringIO()):
                            refresh.refresh(repo,home)
                    backups = sorted((home/'backups').glob('*/*'))
                    with contextlib.redirect_stdout(io.StringIO()):
                        refresh.refresh(repo,home)
                    self.assertEqual(tomllib.loads((home/'config.toml').read_text()), {'model':'local'})
                    self.assertTrue((home/'AGENTS.md').is_symlink())
                    self.assertFalse((repo/'.refresh.journal.json').exists())
                    self.assertEqual(sorted((home/'backups').glob('*/*')), backups)

    def test_crash_then_app_edit_stops_without_overwrite(self):
        atomic = refresh.atomic
        def interrupt(path, data):
            atomic(path, data)
            if path.name == 'config.toml': raise RuntimeError('simulated crash')
        with patch.object(refresh, 'atomic', interrupt):
            with self.assertRaises(RuntimeError): self.run_refresh()
        (self.home/'config.toml').write_text('model="app"\n')
        with self.assertRaisesRegex(ValueError, 'changed during interrupted'):
            self.run_refresh()
        self.assertEqual((self.home/'config.toml').read_text(), 'model="app"\n')
        self.assertTrue((self.repo/'.refresh.journal.json').exists())

    def test_crash_then_instructions_edit_stops_without_overwrite(self):
        agents = self.home / 'AGENTS.md'
        agents.write_bytes(b'Original local instructions\n')
        atomic = refresh.atomic
        def interrupt(path, data):
            atomic(path, data)
            if path.name == '.refresh.journal.json':
                raise RuntimeError('simulated crash')
        with patch.object(refresh, 'atomic', interrupt):
            with self.assertRaises(RuntimeError):
                self.run_refresh()
        agents.write_bytes(b'Post-crash local instructions\n')
        with self.assertRaisesRegex(ValueError, 'Instructions changed during interrupted'):
            self.run_refresh()
        self.assertFalse(agents.is_symlink())
        self.assertEqual(agents.read_bytes(), b'Post-crash local instructions\n')
        self.assertTrue((self.repo / '.refresh.journal.json').exists())
        self.assertEqual(next(p for p in self.backup_files() if p.name == 'AGENTS.md').read_bytes(), b'Original local instructions\n')

    def test_instructions_edit_before_publication_stops(self):
        agents = self.home / 'AGENTS.md'
        agents.write_bytes(b'Original instructions\n')
        backup = refresh.backup
        def edit_after_backup(home, replacements):
            backup(home, replacements)
            agents.write_bytes(b'Updated instructions\n')
        with patch.object(refresh, 'backup', edit_after_backup):
            with self.assertRaisesRegex(ValueError, 'Instructions changed during refresh'):
                self.run_refresh()
        self.assertEqual(agents.read_bytes(), b'Updated instructions\n')
        self.assertFalse(agents.is_symlink())
        self.assertFalse((self.repo / '.refresh.journal.json').exists())

    def test_crash_then_shared_instructions_edit_is_retained(self):
        self.run_refresh()
        atomic = refresh.atomic
        def interrupt(path, data):
            atomic(path, data)
            if path.name == '.refresh.journal.json':
                raise RuntimeError('simulated crash')
        with patch.object(refresh, 'atomic', interrupt):
            with self.assertRaises(RuntimeError):
                self.run_refresh()
        (self.home / 'AGENTS.md').write_bytes(b'Updated shared instructions\n')
        self.run_refresh()
        self.assertTrue((self.home / 'AGENTS.md').is_symlink())
        self.assertEqual((self.repo / 'AGENTS.md').read_bytes(), b'Updated shared instructions\n')
        self.assertFalse((self.repo / '.refresh.journal.json').exists())

    def test_serializer_complete_types(self):
        data = tomllib.loads('''"quoted.key" = "Unicode 😀 and \\u007f"
float=nan
infinity=-inf
when=1979-05-27T07:32:00Z
local=1979-05-27T07:32:00
date=1979-05-27
time=07:32:00
records=[{ path="x", enabled=true }, { path="y", numbers=[1,2.5] }]
[empty]
''')
        self.assertTrue(refresh.equal(refresh.parse(refresh.render(data)), data))

    def test_current_config_read_only_fixture(self):
        path = Path.home()/'.codex/config.toml'
        if not path.exists(): self.skipTest('No current config available')
        original = path.read_bytes()
        (self.repo/'config.template.toml').write_bytes((SOURCE/'codex/config.template.toml').read_bytes())
        (self.home/'config.toml').write_bytes(original)
        self.run_refresh()
        self.assertEqual((self.home/'config.toml').read_bytes(), original)
        self.assertEqual(path.read_bytes(), original)

    def test_shell_codex_only_and_default(self):
        repo = self.root/'shell-repo'
        shutil.copytree(SOURCE, repo, ignore=shutil.ignore_patterns('.git','__pycache__','config.toml','.template.snapshot.toml','.refresh.journal.json','.refresh.lock'))
        home = self.root/'shell-home'
        home.mkdir()
        env = dict(os.environ, HOME=str(home), CODEX_HOME=str(home/'custom-codex'))
        gitbin = self.root/'bin'; gitbin.mkdir()
        git = gitbin/'git'; git.write_text('#!/bin/sh\nexit 0\n'); git.chmod(0o755)
        env['PATH'] = str(gitbin)+os.pathsep+env['PATH']
        subprocess.run([str(repo/'refresh.sh'),'--codex-only'], env=env, check=True, capture_output=True)
        self.assertTrue((home/'custom-codex/config.toml').is_symlink())
        self.assertFalse((home/'.claude').exists())
        subprocess.run([str(repo/'refresh.sh')], env=env, check=True, capture_output=True)
        self.assertTrue((home/'.claude/settings.json').is_symlink())
        (repo/'codex/config.template.toml').write_text('invalid=')
        (home/'.claude/settings.json').unlink()
        (home/'.claude/settings.json').write_text('{"local":true}')
        result = subprocess.run([str(repo/'refresh.sh')], env=env, capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((home/'.claude/settings.json').read_text(),'{"local":true}')
        self.assertFalse((home/'.claude/settings.json').is_symlink())


if __name__ == '__main__':
    unittest.main()

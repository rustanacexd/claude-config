# claude-config

Shared Claude Code and Codex settings, kept in git and symlinked into each app's home directory.

## Set up a machine

Install Python 3.11 or newer on macOS or Linux, then run:

```sh
git clone https://github.com/rustanacexd/claude-config.git ~/code/claude-config
cd ~/code/claude-config
./refresh.sh
```

Restart both apps after setup. Use `./refresh.sh --codex-only` to configure only Codex. The repo can live anywhere.

Claude uses `~/.claude`. Codex uses `CODEX_HOME` when set, otherwise `~/.codex`. Use a separate clone for each machine or Codex home.

| Repository file | Destination |
| --- | --- |
| `settings.json` | `~/.claude/settings.json` |
| `AGENTS.md` | `~/.claude/CLAUDE.md` |
| `pstack-models.md` | `~/.claude/pstack-models.md` |
| `statusline.sh` | `~/.claude/statusline.sh` |
| `output-styles/*.md` | `~/.claude/output-styles/` |
| `skills/*/` | `~/.claude/skills/` |
| `codex/AGENTS.md` | `~/.codex/AGENTS.md` |
| Generated `codex/config.toml` | `~/.codex/config.toml` |

Install plugins, local hooks, and credentials separately. Exa expects `EXA_API_KEY` in your environment. Sessions, caches, authentication, and local-only skills stay untracked.

## Save shared changes

For Claude, run `./refresh.sh`, review the diff, then commit. Refresh adopts real Claude files and new output styles into the repo, then restores their links. Local-only skills and plugin links stay untouched.

For Codex, edit `codex/config.template.toml` for shared settings or `codex/AGENTS.md` for instructions. Run `./refresh.sh --codex-only`, review the diff, then commit.

Keep credentials, project trust, hook state, installation paths, and app-managed settings out of the template. Generated Codex settings and refresh state stay gitignored with owner-only permissions.

## Keep Codex settings local

Change local settings through Codex or `~/.codex/config.toml`. Refresh preserves existing values on first setup and later local edits or deletions. It also repairs links replaced by the app.

Unchanged defaults follow template updates. Local overrides win conflicts. To follow shared defaults again, set the local value to the current template value.

Unchanged settings retain their formatting. Updates may remove comments from the generated file. Run refresh while Codex is idle.

## Restore or recover

Codex backs up files before replacing them under `$CODEX_HOME/backups/`, or `~/.codex/backups/` when unset. Foreign symlink targets stay untouched.

To restore a file, remove its home symlink and copy the backup there. Foreign links include a `.symlink.json` record of their original target.

After an interrupted refresh, rerun the command. If recovery reports changed files, preserve the config, instructions, backups, and `codex/.refresh.journal.json` before reconciling. Once reconciled, remove the journal to start a new merge.

## Test

```sh
python3 -m unittest discover -s tests -v
```

Tests use temporary repositories and app homes.

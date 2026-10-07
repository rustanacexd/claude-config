# claude-config

Shared Claude Code and Codex settings, kept in git and linked into each app's home directory.

## Set up a machine

Install Python 3.11 or newer on macOS or Linux, then clone this repository and run:

```sh
git clone <repository-url> ~/code/claude-config
cd ~/code/claude-config
./refresh.sh
```

Restart Claude Code and Codex after the first setup. The script uses its own location, so you can put the repository anywhere.

To set up only Codex, run:

```sh
./refresh.sh --codex-only
```

Codex uses `CODEX_HOME` when set, otherwise `~/.codex`. Claude uses `~/.claude`. Codex validation runs first, so an invalid Codex template or live config stops setup before Claude adoption.

| Repository file | Destination |
| --- | --- |
| `settings.json` | `~/.claude/settings.json` |
| `CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `pstack-models.md` | `~/.claude/pstack-models.md` |
| `statusline.sh` | `~/.claude/statusline.sh` |
| `output-styles/*.md` | `~/.claude/output-styles/` |
| `skills/*/` | `~/.claude/skills/` |
| `codex/AGENTS.md` | `$CODEX_HOME/AGENTS.md` |
| Generated `codex/config.toml` | `$CODEX_HOME/config.toml` |

Sessions, history, caches, authentication, plugin installations, and local-only skills stay outside the tracked configuration. Provision local hook commands, their trust state, plugin marketplaces with local paths, and credentials on each machine. The Exa default expects `EXA_API_KEY` in your environment. Enable preferences do not install plugins or authenticate services.

## Save shared changes

For Claude, run `./refresh.sh`, review the diff, then commit. Refresh adopts real Claude files into the repository and restores their links. It also adopts new output styles. It never sweeps local Claude skills for adoption. Broken Claude links are removed only when their target belongs to this repository.

For Codex, edit `codex/config.template.toml` for shared defaults or `codex/AGENTS.md` for shared instructions. Run `./refresh.sh --codex-only`, review the diff, then commit. Existing Codex instructions are backed up before the shared instructions replace them.

The template contains portable preferences. Keep project trust, hook state, absolute installation paths, app-managed MCP commands, credentials, skill lists, version records, and onboarding state out of it.

## Keep Codex changes local

Change local settings through Codex or its live `config.toml`. Refresh reads that live file, including a regular file that the app wrote over its symlink, and preserves unknown local sections.

Refresh compares the live config with the last applied template. A value that still equals the previous default follows the new default, including its removal. A local edit or deletion wins a shared change. Deleting a whole table keeps that table absent. Arrays are compared as complete values. Newly introduced defaults fill missing keys, except inside a locally deleted table. The first setup preserves existing values and fills missing defaults.

Refresh reports conflicting key paths without printing values. To return a locally overridden key to shared defaults, set it to the current template value. The next shared change then applies. If a shared key is absent from the template, remove its local value to drop it.

If a refresh changes no settings, it preserves the live config's bytes and comments. A semantic change rewrites the generated file as valid TOML and may remove its comments. Template comments remain tracked.

Generated config, the previous-template snapshot, the recovery journal, temporary files, and the lock stay ignored and have owner-only permissions. They belong to one machine. Use separate clones on different machines or for different `CODEX_HOME` installations.

## Restore backups and interrupted refreshes

Before replacing a regular file or foreign symlink, Codex refresh saves its content under `$CODEX_HOME/backups/<date-and-time>-<unique-suffix>/`. A foreign symlink also gets a `.symlink.json` file recording its original target. Refresh replaces the link itself and leaves the foreign target unchanged. Correct links create no new backups. Backup directories have mode `0700`; backup files have mode `0600`.

To restore an original file, remove its home symlink and copy the matching backup to that home path. For a foreign symlink, recreate the recorded target instead. Run refresh again only when you want to reapply the shared setup.

Refresh journals config, template, and instructions publication. After an interruption, rerun the same command. It finishes the prepared update when the observed files match the recorded before or after versions. If Codex changed config or local instructions changed before their link was installed during that interruption, refresh stops and retains the journal. Edits through an already correct instructions link remain in the shared target. Preserve the live config and instructions, generated file, journal, and backups before reconciling the versions. The journal contains base64 copies of the proposed config and template. After reconciliation, remove the journal to start a new merge, or restore a recorded version and rerun to finish the transaction.

Run refresh while Codex is idle. The refresh lock serializes refresh processes, but Codex does not share that lock. An app write during the short replacement window can race with refresh.

## Test without changing app homes

```sh
python3 -m unittest discover -s tests -v
```

Tests use temporary repositories and app homes. One test reads the current config as a fixture and verifies byte preservation without writing it. The suite covers local edits and deletions, shared updates, backups, foreign symlinks, app link replacement, invalid TOML, interrupted publication, and both shell setup paths.

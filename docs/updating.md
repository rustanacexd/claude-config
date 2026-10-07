# Update machines

Shared changes flow from a feature checkout through GitHub to each machine's checkout. No automatic synchronization runs between machines. Edits to installed files stay local and do not flow back into the repository.

## Publish and apply shared changes

1. In a feature checkout, edit the tracked configuration, global instructions, model sheets, or skill/plugin declarations. Commit, push, and merge the changes through a pull request.
2. In each machine's clean main checkout, run `git pull --ff-only`. If the checkout has local changes or the pull fails, reconcile them before continuing.
3. Run `python3 manage.py refresh` on macOS or Linux. On Windows run `python manage.py refresh`, `py -3 manage.py refresh`, or `./refresh.ps1`.
4. If `SKILLS.md` added skills, install those entries through `npx skills`. To update existing upstream skills, run `npx skills update -g` on each machine. This list does not pin versions.
5. If plugin declarations changed, run `manage.py bootstrap` to restore missing plugins. Update already-installed plugins through their native managers. Local enablement overrides remain local.
6. Run doctor and inventory, verify any upstream skill changes separately, and report pending requirements.

Edit `CLAUDE.md` for shared Claude instructions and `codex/AGENTS.md` for shared Codex instructions. Claude model choices live in `pstack-models.md`; Codex choices live in `codex/pstack-models.md`. Settings live in `settings.json` and `codex/config.template.toml`. Third-party skill selections live in `SKILLS.md`, and plugin declarations live in `plugins.json`.

## Refresh shared defaults

After pulling changes, run the offline refresh. It updates configuration, global instructions, model sheets, and the two custom skills. Install third-party skills separately through [SKILLS.md](../SKILLS.md).

```sh
python3 manage.py refresh
python3 manage.py refresh --app codex
```

On Windows use `py -3 manage.py refresh`, or `./refresh.ps1`. `./refresh.sh` is a compatibility launcher; `--codex-only` selects Codex.

The default homes are `~/.claude` and `~/.codex`. `CLAUDE_CONFIG_DIR` and `CODEX_HOME` override them. `--home PATH` uses that path directly when selecting one app. For both apps it creates `PATH/claude` and `PATH/codex`, which is useful for an isolated test.

Claude Code uses the root `pstack-models.md`, installed as `~/.claude/pstack-models.md`, with its existing `opus` and `fable` roles. Codex uses `codex/pstack-models.md`, installed as `~/.codex/pstack-models.md`, with its Codex model roles. Edit each sheet independently. Refresh updates an unchanged managed sheet and preserves local edits.

Edit `settings.json` or `codex/config.template.toml` to share a setting. Local app settings never flow into this repository. The three-way merge updates unchanged defaults and keeps local values, unknown keys, deleted settings and arrays. Entire locally deleted tables remain deleted. Identical refreshes preserve config bytes and file mtimes and create no new backups.

For a local proxy or credential profile, create `portable.local.json` inside the relevant app home. It is a JSON object using that app's settings shape, including `env` for Claude when needed. Its values remain machine-local. Do not commit credentials or machine endpoints to shared templates. Fresh shared defaults use native app login.

## Install and update third-party skills

Ask your setup agent to follow [SKILLS.md](../SKILLS.md). It lists upstream repositories and exact skill names with grouped `npx skills add` commands for Claude Code and Codex. The repository stores that list rather than upstream skill contents. Plugin-provided skills remain owned by their native plugins.

Use the upstream CLI to inspect or update the installed third-party skills.

```sh
npx skills list -g -a claude-code codex
npx skills update -g
```

Review updates before using them. These commands use upstream versions and require Node/npm and network access. Configuration refresh stays offline.

## Restore and update plugins

After adding plugin declarations to `plugins.json`, run bootstrap on each machine.

```sh
python3 manage.py bootstrap
```

On Windows use `py -3 manage.py bootstrap`, or `python manage.py bootstrap` if the launcher is unavailable. Bootstrap restores missing plugins and preserves local enablement overrides. Use each app's native plugin manager to update plugins that are already installed. Declaration versions record an observed inventory and do not pin native installations.

OpenAI app-provided plugins need a compatible Codex app. Remote connectors need their account connections. Resolve pending capabilities through native app flows, then rerun doctor and inventory.

## Inspect the result

```sh
python3 manage.py inventory
python3 manage.py doctor
```

Both commands are read-only. They compare declared plugins with native inventory, report enabled state and observed versions, and report required environment variables. They check the two custom skills and point you to `SKILLS.md` for third-party installation. They do not verify third-party skills. Plugin versions record prior observations, not a promise of pinned native restoration. Missing accounts and app-provided plugins remain explicit pending items.

For ownership conflicts, private state, or legacy migration, follow [Recover an installation](recovery.md).

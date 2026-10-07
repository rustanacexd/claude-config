# Portable Claude and Codex setup

This repository owns shared settings, instructions, output styles, two custom skills and intent for 8 Claude plugins and 26 Codex plugins. Installed files and reconciliation state live in each app home. Refresh uses Python 3.11 or newer and regular files on macOS, Linux and Windows. It needs no Bash, jq, Node or symlink privileges.

## Set up a fresh machine

Install Git and Python 3.11 or newer, clone this repository and open its directory. Install Claude Code and Codex using their supported installers, or explicitly request tool installation.

```sh
python3 manage.py bootstrap --install-tools
python3 manage.py doctor
```

On Windows, use Python's launcher.

```powershell
py -3 manage.py bootstrap --install-tools
py -3 manage.py doctor
```

Tool installation uses Windows `winget` with `Anthropic.ClaudeCode` and `OpenAI.Codex`, or `npm install -g` with `@anthropic-ai/claude-code` and `@openai/codex`. Without a supported package manager it fails with setup guidance. Tool installation may require a new terminal before its commands appear on PATH. Install Node/npm to use the Sentry MCP and the third-party skills installer. After bootstrap, ask your agent to follow [SKILLS.md](SKILLS.md) and install its listed skills using `npx skills`. Those commands require network access. Some skills also need tools such as GitHub CLI, Google Cloud CLI, Plannotator, or Bash.

Authenticate each app on the new machine through its native login flow. Set `EXA_API_KEY` and `SENTRY_ACCESS_TOKEN` in the local process environment for the declared MCP servers. Doctor reports presence only, never credential values or an authentication-success claim. The Sentry wrapper runs the pinned `@sentry/mcp-server@0.42.0` against `sentry-hosted.go2.io` for organization `go2`. Bootstrap creates a missing Claude user MCP definition through the native CLI and preserves an existing definition. Codex receives the equivalent default through its config merge.

Bootstrap restores missing native plugins after registering their marketplaces, then observes the installation again. Disabled plugins are still installed. It preserves undeclared plugins. Versions in `plugins.json` record the observed source-machine inventory; native managers may install newer versions. OpenAI app-provided plugins require a compatible Codex app. Remote connectors require their account connections. Bootstrap reports pending capabilities and exits nonzero when setup is incomplete. It never copies plugin caches, OAuth sessions or cloud credentials.

On Windows, plugin commands enable Git's `core.longpaths` only in their child-process environment, so deep plugin trees can clone without changing your Git configuration. Git documents [process-local configuration](https://git-scm.com/docs/git-config#Documentation/git-config.txt-GITCONFIGCOUNT), and Git for Windows documents [long path support](https://github.com/git-for-windows/git/blob/main/Documentation/config/core.adoc).

## Refresh shared defaults

After pulling changes, run the offline refresh. It updates configuration, global instructions, model sheets, and the two custom skills. Install third-party skills separately through [SKILLS.md](SKILLS.md).

```sh
python3 manage.py refresh
python3 manage.py refresh --app codex
```

On Windows use `py -3 manage.py refresh`, or `./refresh.ps1`. `./refresh.sh` is a compatibility launcher; `--codex-only` selects Codex.

The default homes are `~/.claude` and `~/.codex`. `CLAUDE_CONFIG_DIR` and `CODEX_HOME` override them. `--home PATH` uses that path directly when selecting one app. For both apps it creates `PATH/claude` and `PATH/codex`, which is useful for an isolated test.

Claude Code uses the root `pstack-models.md`, installed as `~/.claude/pstack-models.md`, with its existing `opus` and `fable` roles. Codex uses `codex/pstack-models.md`, installed as `~/.codex/pstack-models.md`, with its Codex model roles. Edit each sheet independently. Refresh updates an unchanged managed sheet and preserves local edits.

Edit `settings.json` or `codex/config.template.toml` to share a setting. Local app settings never flow into this repository. The three-way merge updates unchanged defaults and keeps local values, unknown keys, deleted settings and arrays. Entire locally deleted tables remain deleted. Identical refreshes preserve config bytes and file mtimes and create no new backups.

For a local proxy or credential profile, create `portable.local.json` inside the relevant app home. It is a JSON object using that app's settings shape, including `env` for Claude when needed. Its values remain machine-local. Do not commit credentials or machine endpoints to shared templates. Fresh shared defaults use native app login.

## Inspect installation

```sh
python3 manage.py inventory
python3 manage.py doctor
```

Both commands are read-only. They compare declared plugins with native inventory, report enabled state and observed versions, and report required environment variables. They check the two custom skills and point you to `SKILLS.md` for third-party installation. They do not verify third-party skills. Plugin versions record prior observations, not a promise of pinned native restoration. Missing accounts and app-provided plugins remain explicit pending items.

## File ownership and recovery

Each app home owns `.claude-config/baseline.json`, `journal.json`, `lock` and `backups/`. Baselines, backups and journals can contain private local settings; keep the app home private. Python applies private file modes on POSIX. Windows inherits the app-home ACL; choose a private user directory. Runtime state is never stored beside the tracked templates.

Each custom skill owns its listed child files, not its entire directory. Unknown files and edited managed files remain local. Refresh retains local file deletions. When an upstream file disappears, refresh removes the installed file only if its recorded content still matches. Source directories include referenced scripts, examples and nested resources. Third-party skills installed by `npx skills` are outside this installer's ownership. If you installed an earlier version of this branch, refresh removes unchanged files from the former vendored skills and preserves edited or untracked files. Follow `SKILLS.md` after that refresh to restore those skills through the upstream CLI.

Publication uses an OS-backed lock, same-directory temporary files, atomic replacements, durable file writes, backups and a versioned journal. POSIX also syncs directories. Windows uses native byte-range locking and inherits filesystem durability guarantees for directory entries. Interrupted work resumes only if every file still matches its prior observation or intended output. If an app edited a file after interruption, refresh refuses to overwrite it. Preserve the journal and backups, compare its proposed output with the edited files, and reconcile while the app is idle before retrying. There is no automatic rollback over new app edits.

Old configuration and instruction symlinks become regular local files without changing their targets. An old Codex baseline is imported only when its config link proves ownership by this clone. A legacy repo-side `.refresh.journal.json` causes refusal. Recover it with the previous installer before upgrading. Linked parents and Windows reparse-point directories below the app home are rejected.

## Install and update third-party skills

Ask your setup agent to follow [SKILLS.md](SKILLS.md). It lists upstream repositories and exact skill names with grouped `npx skills add` commands for Claude Code and Codex. The repository stores that list rather than upstream skill contents. Plugin-provided skills remain owned by their native plugins.

Use the upstream CLI to inspect or update the installed third-party skills.

```sh
npx skills list -g -a claude-code codex
npx skills update -g
```

Review updates before using them. These commands use upstream versions and require Node/npm and network access. Configuration refresh stays offline.

## Run tests

```sh
python3 -m unittest discover -s tests -v
```

Tests use synthetic configs and temporary homes, including paths with spaces. They exercise the actual CLI, repeated refresh, local edits and deletions, nested skill resources, native JSON variations, secret canaries, foreign links, interrupted publication and conflict refusal. GitHub Actions runs Python 3.11 and 3.13 on Ubuntu, macOS and Windows. Symlink fixture tests may skip when the runner cannot create a fixture; ordinary installation still runs without links.

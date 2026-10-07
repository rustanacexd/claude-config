# Set up a machine

Use this guide for a fresh macOS, Linux, or Windows machine. For an existing installation, follow [Update machines](updating.md).

## Follow the setup-agent checklist

Read this guide and [SKILLS.md](../SKILLS.md) before changing a machine.

1. Confirm the requested checkout and app homes. Check Git, Python 3.11 or newer, and Node/npm availability. On macOS and Linux use `python3`; on Windows use `py -3`, or `python` if `py` is unavailable.
2. For a fresh machine, follow the installation steps below and run `manage.py bootstrap`. Use `--install-tools` when tool installation is requested. If bootstrap reports pending items, continue independent setup steps and record each unresolved requirement.
3. Follow every selected install command in `SKILLS.md`. Verify the 19 upstream skills through the Skills CLI and their installed files. `manage.py doctor` does not verify them.
4. Run `manage.py doctor` and `manage.py inventory`. Separate command failures from missing credentials, account connections, and app capabilities. Authenticate through native app flows; keep credentials on the machine.
5. Verify both global instruction files, each app's distinct model sheet, and the two custom skills. Run `manage.py refresh` again and confirm zero changes when no source or local files changed.
6. Report the checkout revision, OS, commands run, observed results, and pending setup. Name any untested behavior. A CI result does not prove a run on the user's connected machine.

## Install the shared setup

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

Tool installation uses Windows `winget` with `Anthropic.ClaudeCode` and `OpenAI.Codex`, or `npm install -g` with `@anthropic-ai/claude-code` and `@openai/codex`. Without a supported package manager it fails with setup guidance. Install Node/npm to use the Sentry MCP and the third-party skills installer. After bootstrap, ask your agent to follow [SKILLS.md](../SKILLS.md) and install its listed skills using `npx skills`. Those commands require network access. Some skills also need tools such as GitHub CLI, Google Cloud CLI, Plannotator, or Bash.

Authenticate each app on the new machine through its native login flow. Set `EXA_API_KEY` and `SENTRY_ACCESS_TOKEN` in the local process environment for the declared MCP servers. Doctor reports presence only, never credential values or an authentication-success claim. The Sentry wrapper runs the pinned `@sentry/mcp-server@0.42.0` against `sentry-hosted.go2.io` for organization `go2`. Bootstrap creates a missing Claude user MCP definition through the native CLI and preserves an existing definition. Codex receives the equivalent default through its config merge.

`plugins.json` declares 8 Claude plugins and 26 Codex plugins, including app-provided and remote plugins. Bootstrap restores missing native plugins after registering their marketplaces, then observes the installation again. Disabled plugins are still installed. It preserves undeclared plugins. Versions in `plugins.json` record the observed source-machine inventory; native managers may install newer versions. OpenAI app-provided plugins require a compatible Codex app. Remote connectors require their account connections. Bootstrap reports pending capabilities and exits nonzero when setup is incomplete. It never copies plugin caches, OAuth sessions or cloud credentials.

On Windows, plugin commands enable Git's `core.longpaths` only in their child-process environment, so deep plugin trees can clone without changing your Git configuration. Git documents [process-local configuration](https://git-scm.com/docs/git-config#Documentation/git-config.txt-GITCONFIGCOUNT), and Git for Windows documents [long path support](https://github.com/git-for-windows/git/blob/main/Documentation/config/core.adoc).

If `py` is unavailable on Windows, use `python` in the commands above. Verify that `python --version` reports Python 3.11 or newer. After a tool installation changes PATH, open a new terminal before retrying bootstrap.

To use tools already installed on the machine, omit `--install-tools`.

```sh
python3 manage.py bootstrap
```

## Select the app homes

The default homes are `~/.claude` and `~/.codex`. `CLAUDE_CONFIG_DIR` and `CODEX_HOME` override them. `--app claude` or `--app codex` selects one app. `--home PATH` uses that path directly when selecting one app. For both apps it creates `PATH/claude` and `PATH/codex`.

These options redirect the Python installer. They do not redirect global `npx skills` commands. Read [SKILLS.md](../SKILLS.md) before installing third-party skills into a test environment.

## Verify the installation

```sh
python3 manage.py inventory
python3 manage.py doctor
```

Both commands are read-only. They compare declared plugins with native inventory, report enabled state and observed versions, and report required environment variables. They check the two custom skills and point you to `SKILLS.md` for third-party installation. They do not verify third-party skills. Plugin versions record prior observations, not a promise of pinned native restoration. Missing accounts and app-provided plugins remain explicit pending items.

Confirm that Claude has `CLAUDE.md` and its own `pstack-models.md`. Confirm that Codex has `AGENTS.md` and its distinct `pstack-models.md`. Each app receives the custom `show-me` and `explain-diff-html` skills. Run refresh a second time and expect zero changes when the source and installed files have not changed.

For future changes, follow [Update machines](updating.md). For interrupted writes or ownership conflicts, follow [Recover an installation](recovery.md).

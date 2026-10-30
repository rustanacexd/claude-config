# Claude Code and Codex config

My global config for Claude Code and Codex: instructions, settings, pstack model sheets, custom skills, and plugins.

## Install

Needs Python 3.11 or newer. Run this from the checkout on any machine, and again after every pull:

```sh
python3 install.py
```

On Windows, run `py -3 install.py`.

The installer:

- Copies the instructions, model sheets, status line, merge guard, Orca cookie guard, and skills into `~/.claude` and `~/.codex`.
- Lays `claude/settings.json` over `~/.claude/settings.json` and `codex/config.template.toml` over `~/.codex/config.toml`. Keys set here win. Keys that exist only on the machine, such as a local proxy or credentials, stay.
- Points the Bash tool at Homebrew bash (`env.CLAUDE_CODE_SHELL` in `claude/settings.json`), so inline commands use bash syntax instead of zsh's. Where `/opt/homebrew/bin/bash` doesn't exist (Windows, Linux, Intel Macs), Claude Code ignores the setting and picks its shell as before.
- Runs gcloud in Claude sessions on its application-default credentials (`env.CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE`) when `gcloud auth application-default login` has written them. A Workspace session-length policy expires the normal gcloud sign-in, and an agent can't answer the reauthentication prompt. Without the file, the setting is removed.
- Installs missing enabled plugins with the `claude` and `codex` CLIs.
- Installs missing third-party skills with `npx skills`.

A step whose CLI is not on `PATH` is skipped with a message. `CLAUDE_CONFIG_DIR` and `CODEX_HOME` override the default homes.

The installer disables a plugin through its `enabled = false` config entry and never uninstalls it. `codex plugin list` still reports a disabled remote plugin as enabled, because it shows the account installation, not the config flag.

## Change something

Edit the file here, then run `python3 install.py`. Don't edit the installed copies, because the next install overwrites them.

# Claude Code and Codex config

My global config for Claude Code and Codex: instructions, settings, pstack model sheets, custom skills, and plugins.

## Install

Needs Python 3.11 or newer. Run this from the checkout on any machine, and again after every pull:

```sh
python3 install.py
```

On Windows, run `py -3 install.py`.

It does five things:

- Copies the instructions, model sheets, status line, merge guard, plugin updater, and skills into `~/.claude` and `~/.codex`.
- Lays `settings.json` over `~/.claude/settings.json` and `codex/config.template.toml` over `~/.codex/config.toml`. Keys set here win. Keys that exist only on the machine, such as a local proxy or credentials, stay.
- Installs missing enabled plugins with the `claude` and `codex` CLIs.
- Installs missing third-party skills with `npx skills`.
- On macOS, schedules a launchd job that updates every installed Claude Code and Codex plugin every 12 hours. It logs to `~/Library/Logs/claude-config-update-plugins.log`.

A step whose CLI is not on `PATH` is skipped with a message. `CLAUDE_CONFIG_DIR` and `CODEX_HOME` override the default homes.

## Change something

Edit the file here, then run `python3 install.py`. Don't edit the installed copies, because the next install overwrites them.

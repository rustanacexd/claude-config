# Claude Code and Codex config

My global config for Claude Code and Codex: instructions, settings, pstack model sheets, custom skills, and plugins.

## Install

Needs Python 3.11 or newer. Run this from the checkout on any machine, and again after every pull:

```sh
python3 install.py
```

On Windows, run `py -3 install.py`.

The installer:

- Copies the instructions, model sheets, status line, merge guard, and skills into `~/.claude` and `~/.codex`.
- Lays `settings.json` over `~/.claude/settings.json` and `codex/config.template.toml` over `~/.codex/config.toml`. Keys set here win. Keys that exist only on the machine, such as a local proxy or credentials, stay.
- Installs missing enabled plugins with the `claude` and `codex` CLIs.
- Removes enabled Codex plugins from `openai-curated-remote` explicitly set to `false`, then verifies their effective state with `codex plugin list --marketplace openai-curated-remote --json`.
- Installs missing third-party skills with `npx skills`.

A step whose CLI is not on `PATH` is skipped with a message. `CLAUDE_CONFIG_DIR` and `CODEX_HOME` override the default homes.

Remote plugin removal applies to the signed-in account. [Codex removes the account installation and cached bundle](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/cli/src/plugin_cmd.rs#L655-L680); local config flags alone do not change that account state. The installer fails if removal or verification fails. The service can refuse removal of installed-by-default plugins, as observed for Pages and Sites, leaving them enabled.

## Change something

Edit the file here, then run `python3 install.py`. Don't edit the installed copies, because the next install overwrites them.

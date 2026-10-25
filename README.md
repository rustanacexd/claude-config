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
- Lays `claude/settings.json` over `~/.claude/settings.json` and `codex/config.template.toml` over `~/.codex/config.toml`. Keys set here win. Keys that exist only on the machine, such as a local proxy or credentials, stay.
- Installs missing enabled plugins with the `claude` and `codex` CLIs.
- Installs missing third-party skills with `npx skills`.

A step whose CLI is not on `PATH` is skipped with a message. `CLAUDE_CONFIG_DIR` and `CODEX_HOME` override the default homes.

## Pstack effort

Every agent dispatch uses the calling session's current effort. The installer adds
`pstack_effort.py` as a PreToolUse hook in both runtimes. It rewrites only the effort
argument, preserves the selected model, and blocks dispatch if the live effort
cannot be read. It applies to all Agent and spawn_agent calls because pstack also
uses built-in agent types. The model sheets override pstack's task-based effort
adjustments.

Claude Code supplies the live effort in its [hook input](https://code.claude.com/docs/en/hooks).
Codex reads the effort from the transcript entry matching the current turn ID.
This avoids reading a saved default or an earlier turn's effort. The installer
also removes saved effort overrides for the three pinned Claude model versions,
while preserving their other settings.

After installation, review and trust the new Codex hook through `/hooks`.
[Codex skips untrusted hooks](https://developers.openai.com/codex/hooks).
The hook requires a runtime that supports agent input rewriting. Existing chats
may need to reload their hooks before the new policy applies.

Run the hook and migration checks with `python3 -m unittest discover -s tests`.

For opt-in live verification, run
`python3 tools/verify_pstack_effort.py --output-dir <temporary-directory>`.
This consumes model usage. It requests a deliberately different child effort,
then checks the persisted parent and child runtime records at `medium` and `high`.
The Codex probe uses only the installed effort hook in an isolated invocation,
with hook trust bypassed for that reviewed test. It does not change persistent
hook trust. Normal sessions still require `/hooks` approval.

The installer disables a plugin through its `enabled = false` config entry and never uninstalls it. `codex plugin list` still reports a disabled remote plugin as enabled, because it shows the account installation, not the config flag.

## Change something

Edit the file here, then run `python3 install.py`. Don't edit the installed copies, because the next install overwrites them.

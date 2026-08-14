# claude-config

My Claude Code config, kept in git and symlinked into `~/.claude`.

## What is here

| File | Goes to |
| --- | --- |
| `settings.json` | `~/.claude/settings.json` |
| `CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `statusline-command.sh` | `~/.claude/statusline-command.sh` |
| `output-styles/*.md` | `~/.claude/output-styles/` |
| `skills/*/` | `~/.claude/skills/` |

Nothing else from `~/.claude` is tracked. Sessions, history, caches, plugins,
and skills not in this repo stay local.

## Set up a new machine

1. Clone this repo: `git clone <url> ~/code/claude-config`
2. Run `~/code/claude-config/refresh.sh`
3. Restart Claude Code.

The script makes the symlinks. Put the repo anywhere. The script uses its own
location.

## Save a change

Run `./refresh.sh`, then commit.

The script does two things:

- It moves real files out of `~/.claude` into the repo, then symlinks them
  back. This picks up an output style that you made in the Claude Code UI.
- It creates any symlink that is missing.

Run it as often as you want. It skips links that are already correct.

## Limits

- The script does not delete. If you remove a file from the repo, delete the
  old symlink in `~/.claude` yourself.
- `settings.json` has two absolute paths under `/Users/rustancorpuz/`: the
  status line command and a subagent hook. Edit them if your username differs.

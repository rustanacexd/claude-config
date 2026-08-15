# claude-config

My Claude Code config, kept in git and symlinked into `~/.claude`.

## What is here

| File | Goes to |
| --- | --- |
| `settings.json` | `~/.claude/settings.json` |
| `CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `statusline.sh` | `~/.claude/statusline.sh` |
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

The script deletes only broken symlinks that point back into this repo. Real
files, plugin symlinks, and local-only skills in `~/.claude` are left alone.

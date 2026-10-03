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
| `gates/` | `~/.claude/gates` |

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

## Turn the workflow gates off or on

The hooks in `settings.json` run the workflow gates in `gates/` on every tool
call. To turn every gate off, run:

```sh
touch ~/.claude/gates.off
```

To turn them back on, run:

```sh
rm ~/.claude/gates.off
```

The change takes effect on the next tool call. You do not need to restart
Claude Code or edit `settings.json`. While the file exists, every gate exits at
once and Python never starts. `gates/README.md` describes each gate.

## Limits

The script deletes only broken symlinks that point back into this repo. Real
files, plugin symlinks, and local-only skills in `~/.claude` are left alone.

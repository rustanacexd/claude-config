# Global instruction ownership

This repository owns `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and the other files `install.py` copies.
Edit them here. Do not edit the installed copies directly.
Files for `~/.claude` live in `claude/`, files for `~/.codex` in `codex/`, and skills for both in `skills/`.
Keep `CLAUDE.md` out of the repo root and `.claude/`: Claude Code reads this file only when neither exists.

After every commit or push here, run `python3 install.py` so the live config matches the repo.
The installer runs and reads the working tree, not the commit: if `git status` shows uncommitted
edits you did not make, stop and ask before running it.
The installer does not delete a skill removed from the repo. Delete its installed copies under the
`skills/` directories of `CLAUDE_CONFIG_DIR` and `CODEX_HOME` (default `~/.claude` and `~/.codex`) yourself.

# Global instruction ownership

This repository owns `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and the other files `install.py` copies.
Edit them here. Do not edit the installed copies directly.
The source of `~/.claude/CLAUDE.md` is `claude/CLAUDE.md`. Keep `CLAUDE.md` out of the repo root and `.claude/`:
Claude Code reads this `AGENTS.md` only when neither exists.

After every commit or push here, run `python3 install.py` so the live config matches the repo.
The installer copies the working tree, not the commit: if `git status` shows uncommitted edits
you did not make to files it copies, stop and ask before running it.
The installer does not delete a skill removed from the repo. Delete its installed copies under
`~/.claude/skills` and `~/.codex/skills` yourself.

# Testing

- Do not add unit tests unless I explicitly request them.
- Prefer existing E2E or integration checks and verification against the real application.
- For small fixes, keep one-off verification scripts and artifacts outside the repository.
- Do not add testing frameworks, harnesses, or suites unless I explicitly request them.
- If you must test a system in isolation, first write down all the ways it could fail, then write the code.
- A test that breaks under a behavior-preserving refactor is asserting implementation, not behavior. Do not add it.
- Never delete or weaken a failing test to make the suite pass. Fix the code, or ask.

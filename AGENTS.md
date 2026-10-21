# Global instruction ownership

This repository owns `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and the other files `install.py` copies.
Edit them here, then run `python3 install.py`. Do not edit the installed copies directly.

# Testing

- Do not add unit tests unless I explicitly request them.
- Prefer existing E2E or integration checks and verification against the real application.
- For small fixes, keep one-off verification scripts and artifacts outside the repository.
- Do not add testing frameworks, harnesses, or suites unless I explicitly request them.
- If you must test a system in isolation, first write down all the ways it could fail, then write the code.
- A test that breaks under a behavior-preserving refactor is asserting implementation, not behavior. Do not add it.
- Never delete or weaken a failing test to make the suite pass. Fix the code, or ask.

# Global instruction ownership

This repository owns `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`.
Before changing either file, read `README.md` and `docs/updating.md`.
Edit `CLAUDE.md` and `codex/AGENTS.md` here, then run
`python3 manage.py refresh` and `python3 manage.py check-sync`.
Do not edit the installed copies directly.

# Testing

- Never write unit tests after you write code.
- Highly prefer E2E or integration tests as the sole testing mechanism. Use them to verify complex features work. At the end of those tests, produce a verifiable and repeatable artifact.
- If you must test a system in isolation, first write down all the ways it could fail, then write the code.
- A test that breaks under a behavior-preserving refactor is asserting implementation, not behavior. Do not add it.
- Never delete or weaken a failing test to make the suite pass. Fix the code, or ask.

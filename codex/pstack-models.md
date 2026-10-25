# pstack model configuration

Per-role model overrides for pstack. `default effort: session` means strict inheritance from the calling session, enforced at dispatch by the installed PreToolUse hook. The rules below override pstack's default effort adjustments. `session hook: on` enables pstack's routing instruction.

feature, refactoring: gpt-6.1-sol
bug-fix: gpt-6.1-sol
perf-issue: gpt-6.1-sol
hillclimb: gpt-6.1-sol
judgment and prose: gpt-6.1-sol
strongest judgment: gpt-6-astra
how explorer: gpt-6.1-sol
how explainer: gpt-6.1-sol
why investigators: gpt-6.1-sol
why synthesizer: gpt-6.1-sol
reflect tooling: gpt-6.1-sol
reflect judgment, divergent, synthesizer: gpt-6.1-sol
arena runners: gpt-6-astra, gpt-6.1-sol
arena cross-judge pool: gpt-6-astra, gpt-6.1-sol
swarm workers: gpt-6.1-sol
architect runners: gpt-6-astra, gpt-6.1-sol
interrogate reviewers: gpt-6-astra, gpt-6.1-sol

default effort: session
session hook: on

## Strict session effort

Every pstack agent must use the calling session's current effort. This overrides
pstack's task-based effort adjustments and its instruction to omit effort for
`session`. Keep each role's configured model. Do not substitute a model default,
raise or lower effort, or reuse an effort value from an earlier turn.

The installed `pstack_effort.py` PreToolUse hook enforces this at each dispatch.
Claude Code supplies the live effort in the hook event. Codex reads the matching
current `turn_context` from the transcript and passes it as `reasoning_effort`.
If the live effort cannot be determined, the hook blocks the dispatch. Do not
bypass the hook or retry with a different effort. Report unsupported levels.

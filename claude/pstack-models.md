# pstack model configuration

Per-role model overrides for pstack. `default effort: session` means strict inheritance from the calling session, enforced at dispatch by the installed PreToolUse hook. The rules below override pstack's default effort adjustments. `session hook: on` enables pstack's routing instruction.

feature, refactoring: opus
bug-fix: opus
perf-issue: opus
hillclimb: opus
judgment and prose: opus
strongest judgment: fable
how explorer: opus
how explainer: opus
why investigators: opus
why synthesizer: opus
reflect tooling: opus
reflect judgment, divergent, synthesizer: opus
arena runners: opus, fable, sonnet
arena cross-judge pool: opus, fable, sonnet
swarm workers: opus
architect runners: opus, fable, sonnet
interrogate reviewers: opus, fable, sonnet

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

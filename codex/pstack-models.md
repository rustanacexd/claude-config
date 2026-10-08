# pstack model configuration

Per-role model overrides for pstack skills. Each pstack SKILL.md names its defaults in a Models section; the values here override those defaults. Delete a line to fall back to the skill default. A value of `inherit-parent` or `auto` runs that role on the parent session's model (the `Agent` call omits `model`); an alias entry in a panel list still counts toward that panel's fan-out. A model may carry a reasoning effort, as in `gpt-6.1-sol @xhigh` (levels: low, medium, high, xhigh, max); the role then runs through the pstack effort agent of that level, each entry of a panel list on its own. `default effort` sets the level for a value without one; `session` keeps the parent session's effort. `session hook: off` stops the Claude Code or Codex SessionStart hook, or the pstack Pi extension, from injecting the poteto-mode mandate; any other value, or no line, leaves it on.

feature, refactoring: gpt-6.1-sol
bug-fix: gpt-6.1-sol
perf-issue: gpt-6.1-sol
hillclimb: gpt-6.1-sol
judgment and prose: gpt-6.1-sol
strongest judgment: gpt-6.1-sol
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

# Cross-model work

Codex models are one family and Claude models are another. Every pstack role runs on the
Codex models in the pstack model configuration above. Use Claude only when a pstack skill
asks for a different model family or a model-diverse panel. Architect runners, interrogate
reviewers, and arena runners and judges each include one Claude Opus 5.5 member and one
Claude Fable 5.1 member alongside the Codex models. Dispatch both through T3's
`delegate_task` with provider instance `claudeAgent`. Use model `claude-opus-5-5`
at medium effort for Opus and model `claude-fable-5-1` at medium effort for Fable.
If either Claude model is unavailable or out of credits, skip that member and continue.
If Claude is unavailable or out of credits entirely, use only `gpt-6-astra` and
`gpt-6.1-sol` for all panel work, including runners, reviewers, and judges. Single-model
roles continue on `gpt-6.1-sol`. This fallback satisfies cross-family requirements when
Claude cannot run. Do not block the workflow or keep retrying Claude after a confirmed
credit failure. Say in the reply which Claude models were skipped and that the Codex
fallback was used.

# pstack model configuration

Per-role model overrides for pstack skills. Each pstack SKILL.md names its defaults in a Models section; the values here override those defaults. Delete a line to fall back to the skill default. A value of `inherit-parent` or `auto` runs that role on the parent session's model (the `Agent` call omits `model`); an alias entry in a panel list still counts toward that panel's fan-out. A model may carry a reasoning effort, as in `gpt-6.1-sol @xhigh` (levels: low, medium, high, xhigh, max); the role then runs through the pstack effort agent of that level, each entry of a panel list on its own. `default effort` sets the level for a value without one; `session` keeps the parent session's effort. `session hook: off` stops the Claude Code or Codex SessionStart hook, or the pstack Pi extension, from injecting the poteto-mode mandate; any other value, or no line, leaves it on.

feature, refactoring: gpt-6.1-sol @high
bug-fix: gpt-6.1-sol @xhigh
perf-issue: gpt-6.1-sol @high
hillclimb: gpt-6.1-sol @high
judgment and prose: gpt-6.1-sol @medium
strongest judgment: gpt-6-astra @high
how explorer: gpt-6.1-sol @medium
how explainer: gpt-6.1-sol @medium
why investigators: gpt-6.1-sol @medium
why synthesizer: gpt-6.1-sol @medium
reflect tooling: gpt-6.1-sol @medium
reflect judgment, divergent, synthesizer: gpt-6.1-sol @high
arena runners: gpt-6-astra @high, gpt-6.1-sol @high, gpt-6-luna @high
arena cross-judge pool: gpt-6-astra @high, gpt-6.1-sol @high, gpt-6-luna @high
swarm workers: gpt-6.1-sol @medium
architect runners: gpt-6-astra @high, gpt-6.1-sol @high, gpt-6-luna @high
interrogate reviewers: gpt-6-astra @high, gpt-6.1-sol @high, gpt-6-luna @high

default effort: session
session hook: on

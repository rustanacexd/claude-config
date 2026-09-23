# pstack model configuration

Per-role model overrides for pstack skills. Each pstack SKILL.md names its defaults in a Models section; the values here override those defaults. Delete a line to fall back to the skill default. A value of `inherit-parent` or `auto` runs that role on the parent session's model (the `Agent` call omits `model`); an alias entry in a panel list still counts toward that panel's fan-out. `session hook: off` stops the Claude Code or Codex SessionStart hook from injecting the poteto-mode mandate; any other value, or no line, leaves it on.

feature, refactoring: claude-opus-5-5
bug-fix: claude-fable-5-1
perf-issue: claude-fable-5-1
hillclimb: claude-fable-5-1
judgment and prose: claude-opus-5-5
strongest judgment: claude-fable-5-1
how explorer: claude-opus-5-5
how explainer: claude-opus-5-5
why investigators: claude-opus-5-5
why synthesizer: claude-opus-5-5
reflect tooling: claude-opus-5-5
reflect judgment, divergent, synthesizer: claude-opus-5-5
arena runners: claude-opus-5-5, claude-fable-5-1, claude-sonnet-5
arena cross-judge pool: claude-opus-5-5, claude-fable-5-1, claude-sonnet-5
swarm workers: claude-opus-5-5
architect runners: claude-opus-5-5, claude-fable-5-1, claude-sonnet-5
interrogate reviewers: claude-opus-5-5, claude-fable-5-1, claude-sonnet-5

session hook: on

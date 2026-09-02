# pstack model configuration

Per-role model overrides for pstack skills. Each pstack SKILL.md names its defaults in a Models section; the values here override those defaults. Delete a line to fall back to the skill default. A value of `inherit-parent` or `auto` runs that role on the parent session's model (the `Agent` call omits `model`); an alias entry in a panel list still counts toward that panel's fan-out.

The `Agent` tool in this environment accepts only the family aliases `opus`, `sonnet`, `haiku`, `fable`. Versioned slugs such as `claude-opus-5` fail validation, so every value below is an alias. Aliases resolve to each family's current default (Opus 5, Sonnet 5, Haiku 4.5, Fable 5.1); pinning an older point release is not possible here.

feature, refactoring: opus
bug-fix: fable
perf-issue: fable
hillclimb: fable
judgment and prose: opus
strongest judgment: fable
how explorer: opus
how explainer: opus
how critics: opus, fable, sonnet
why investigators: opus
why synthesizer: opus
reflect tooling: opus
reflect judgment, divergent, synthesizer: opus
arena runners: opus, fable, sonnet
arena cross-judge pool: opus, fable, sonnet
swarm workers: opus
architect runners: opus, fable, sonnet
interrogate reviewers: opus, fable, sonnet

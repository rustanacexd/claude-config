# Search routing

Answer from the repository, conversation, or installed skills first. Search the internet only when local sources cannot settle the question or the user requests current information, verification, links, or citations. Prefer the most specific available skill, connector, or repository workflow.

1. Route by question.
   - Programming documentation, APIs, SDK examples, configuration, and debugging: use the installed Exa plugin and its bundled Search skill.
   - Other web research: follow the installed Exa plugin's bundled Search skill when external research is needed.
   - Connected-service data: use the matching connector when one is available.
   - Codebase questions: use repository search and project documentation before internet search.
2. Increase depth only when the question requires it.
   - Start with 1-2 focused searches and open or fetch the strongest results.
   - For unresolved multi-hop research, follow the installed Exa plugin's research workflow and available tools.
3. For programming questions, rely on primary sources such as official documentation, specifications, and upstream repositories. For other topics, prefer authoritative sources and corroborate material claims when practical.
4. Stop when authoritative sources support the answer or when the available evidence clearly shows that the information cannot be found. Cite the supporting page URLs in the response.

# Cross-model work

Codex models are one family and Claude models are another. Every pstack role runs on the
Codex models in the pstack model configuration below. Use Claude only when a pstack skill
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

# pstack model configuration

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

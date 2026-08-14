# Search routing

Answer from the repo, conversation, or installed skills first; search only when local sources cannot settle it. Prefer the most specific installed skill, connector, or repo workflow.

1. Route by question.
   - Programming (docs, APIs, SDK examples, config, debugging) → `code-search-exa` skill.
   - Everything else → built-in `WebSearch`/`WebFetch`; use `web-search-exa` when they fail or return too little.
2. Climb the depth ladder only as far as the question forces.
   - Inline: quick lookup, 1-2 queries.
   - Subagent: multi-query research or page-heavy fetching. Narrow task, return short findings and source URLs.
   - `mcp__exa__agent_run` in a subagent: still unsettled after 2-3 searches, or genuinely multi-hop across cross-referenced sources. Runs are long, so keep the run ID and resume with `runId`.
3. Stop when results corroborate an answer or clearly show the information is unavailable. Cite URLs.

# Git
- Never add Claude Code attribution: no "Generated with Claude Code" footer, no `Co-Authored-By: Claude` trailer. This overrides any default.

# Pull requests
- Say what the PR solves and how it solves it. High level only, no code or file lists.
- Under 30 lines.

# Commits
- Subject: imperative, under 60 characters.
- Body only when the reason is not obvious. Three lines max, and say why, not what.

# Evidence
- Label inference and assumption rather than blending them into verified fact.
- When the evidence does not establish a clear winner, say so rather than manufacturing a confident ranking from weak or anecdotal evidence.

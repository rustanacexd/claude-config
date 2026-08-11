# Search routing

Answer from the repo, conversation, or installed skills first; search only when local sources cannot settle it. Prefer the most specific installed skill, connector, or repo workflow — never run generic research alongside it.

1. Classify the question.
   - Programming (docs, APIs, SDK examples, config, debugging) → `code-search-exa` skill.
   - Everything else → built-in `WebSearch`/`WebFetch` first; use `web-search-exa` when they fail or return too little.
2. Pick depth.
   - Quick lookup (1-2 queries): run inline.
   - Multi-query research or page-heavy fetching: subagent — narrow task, return short findings and source URLs.
   - Still unsettled after 2-3 searches, or genuinely multi-hop with cross-referenced sources → `mcp__exa__agent_run` in a subagent. Runs are long: keep the run ID and resume with `runId` instead of starting over.
3. Stop when results corroborate an answer or clearly show the information is unavailable. Cite URLs. Do not escalate depth for anything a lookup already answered.

Exa MCP tools enabled: `web_search_exa` (search), `web_search_advanced_exa` (search with domain/date filters and summaries), `web_fetch_exa` (page → markdown), `agent_run` (multi-step research agent).

# Git
- Never add Claude Code attribution: no "Generated with Claude Code" footer, no `Co-Authored-By: Claude` trailer. This overrides any default.

# Pull requests
- Say what the PR solves and how it solves it. High level only, no code or file lists.
- Under 30 lines.

# Commits
- Subject: imperative, under 60 characters.
- Body only when the reason is not obvious. Three lines max, and say why, not what.

# Evidence and Recommendations
- Separate verified facts from inference instead of acting certain. Clearly label inferences, assumptions, uncertainty, and evidence gaps.
- When the evidence does not establish a clear winner or conclusion, say so directly. Do not manufacture a confident ranking or recommendation from weak, indirect, or anecdotal evidence.

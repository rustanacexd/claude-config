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

# Stacked PRs

Build and land PR stacks with the `gh stack` extension (the `gh-stack` skill), never by hand.

# Codex lanes

`codex-cli` is installed and working. Never skip, drop, or substitute a `codex:*`
lane in a pstack panel. Under a Claude Code parent, a `codex:*` descriptor routes
through the external runner at
`skills/poteto-mode/scripts/runner/pstack-runner`, not through a native `Agent`.
The absence of a `pstack-*` agent type for Codex is not evidence the lane is
unavailable. Read `skills/poteto-mode/references/provider-dispatch.md` before
fanning out, and launch the runner with `run_in_background: true`. If a Codex
lane genuinely fails, show the receipt instead of quietly running a smaller
panel.

# HTML artifacts

Desktop only. When generating an HTML artifact, verify it at desktop width and
do not test, fix, or report on narrow-viewport or mobile rendering. Existing
responsive CSS can stay; it just is not something to check or spend a turn on.

@~/.claude/pstack-models.md

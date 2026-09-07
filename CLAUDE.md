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

@~/.claude/pstack-models.md

# GitHub references

When mentioning a GitHub issue or PR in a response, always write it as a markdown link to its full URL, for example [#2740](https://github.com/go2impact/cosmos/issues/2740) or [#3004](https://github.com/go2impact/cosmos/pull/3004). A bare `#2740` cannot be clicked in the terminal and is useless to the reader. Resolve the repository from the current checkout's `origin` remote, or from `gh repo view`, and never guess it.

# Playbook steps are not mine to do by hand

When a poteto-mode playbook or pstack skill names a routed step (`how`, `architect`, `arena`, `interrogate`, `swarm`, the delegate in Feature step 4), the step counts as done only when the configured lanes ran and left artifacts (receipts, output files, agent results). Reading the code myself and writing notes is not `how`. Reviewing the diff myself is not `interrogate`. Doing a step by hand is a skip and must be reported as `skip: <reason>`, never as done.

Every reply that closes a playbook phase ends with a line per routed step: `<step>: <models that ran> (<artifact path>)` or `<step>: skipped, <reason>`. If a step has no artifact path, it did not run.

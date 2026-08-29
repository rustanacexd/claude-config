---
name: code-search-exa
description: Programming research using Exa MCP. Use for library, SDK, and API documentation lookup; real code, config, and framework usage examples; and debugging an exact error string against current technical sources.
context: fork
---

# Code Search Exa

Use Exa for programming-related search when authoritative snippets, current docs, or real examples would improve the answer.

## Tool Selection

Start with `mcp__exa__web_search_exa`.

When a result's URL looks relevant but its snippet is too thin, read it with `mcp__exa__web_fetch_exa` (batch multiple URLs in one call) or the built-in `WebFetch`.

For structured, multi-hop, or deep technical research that a few searches will not settle, use `mcp__exa__agent_run` — the Exa Agent. Runs can take several minutes: keep the returned `agent_run_...` ID and resume with `runId` rather than starting a duplicate run.

Exa tools missing from the tool list, or setting up the MCP server → [`mcp-setup.md`](mcp-setup.md).

## Context Isolation

This skill runs in a forked context (`context: fork`), so Exa's noisy or numerous results stay out of the main conversation. Keep the search narrow and self-contained, then return only:

- Minimal copyable snippets.
- Version constraints, setup assumptions, and gotchas.
- Source URLs.

Deduplicate near-identical results such as mirrors, forks, repeated StackOverflow answers, and duplicate docs pages before returning.

## Query Rules

Write semantic queries that describe the ideal technical source.

Always include:

- Programming language, when relevant.
- Framework and version, when known.
- Exact identifiers, config keys, package names, function/class names, CLI commands, or error messages from the request.

Examples:

- `Python 3.12 FastAPI lifespan async context manager official docs example`
- `React 19 useActionState form validation minimal example`
- `Go 1.23 slog custom handler GitHub example`
- `Next.js 14 route handler revalidateTag cache invalidation docs`

## Search Depth

Keep searching — refined terms, the exact error string, a specific version, or a `WebFetch` on a promising source — until you hold a snippet whose version matches the request and whose source URL you can cite. A single query rarely pins down correct, current API usage.

## Result Handling

Before presenting results:

1. Deduplicate similar approaches and keep the best representative snippet for each.
2. Prefer official docs, package READMEs, source repositories, and high-quality Q&A with accepted or well-explained answers.
3. Preserve version constraints and setup assumptions.
4. Extract the minimum useful snippet and explain the surrounding requirement, rather than pasting long source text.

## Output Shape

Return:

1. Minimal working snippet or command.
2. Notes on version constraints, setup, and gotchas.
3. Sources as URLs.

For implementation tasks, use the Exa result to inform the code change, then verify locally with the repo's normal tests or type checks when possible.

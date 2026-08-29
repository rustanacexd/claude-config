---
name: web-search-exa
description: Non-programming web research using Exa MCP. Use for current events, news, and dates; company, product, or market research; and fact-checking or source discovery grounded in live external sources.
---

# Web Search Exa

Use Exa for general web research when current or source-grounded information would improve the answer.

For programming docs, API usage, SDK examples, config patterns, or debugging research, use `code-search-exa` instead.

## Tools

Start with `mcp__exa__web_search_exa`.

Reach for `mcp__exa__web_fetch_exa` when a search result's URL is clearly relevant but its snippet is too thin to extract the answer, quote, constraint, or citation you need.

## Query Rules

Write semantic queries that describe the ideal source.

Include the specifics that narrow it:

- Entity names, location, date range, product/version, jurisdiction, or source type.
- The current year or time period, for latest/current requests.
- Words that bias toward official or primary sources, for high-stakes topics.

Examples:

- `official press release OpenAI model release May 2026`
- `primary source California employment law paid sick leave 2026`
- `independent reviews best portable monitor for MacBook 2026 comparison`
- `company pricing page SOC 2 compliance automation platform`

## Search Depth

Keep searching — refined terms, alternate phrasings, or a `mcp__exa__web_fetch_exa` on a promising URL — until two independent sources corroborate the answer, or the results clearly show the information is unavailable. One search rarely settles a non-trivial question.

## Result Handling

Before presenting results:

1. Deduplicate near-identical pages, syndicated articles, mirrors, and SEO copies.
2. Prefer primary sources, official pages, original documents, filings, reputable reporting, and expert analysis.
3. Preserve dates, version constraints, geography, and uncertainty.
4. Summarize and cite URLs rather than pasting long source text.

## Output Shape

Return:

1. Direct answer or recommendation.
2. Key evidence, dates, constraints, and caveats.
3. Sources as URLs.

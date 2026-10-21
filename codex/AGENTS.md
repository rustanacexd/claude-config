# Skills and task tracking

Follow a named skill's supplied instructions or read its SKILL.md and runtime mapping.
Use the current runtime's task tracker.

# T3 Code only

In T3 Code, use Claude Opus, Codex `gpt-6.1-sol`, Codex `gpt-6-astra`, then
Claude Fable for the `arena runners`, `architect runners`, and `interrogate reviewers`
role lists. Follow pstack for workflow, effort, judging, unavailable-model handling,
and review requirements.

For cross-provider members, use T3's `delegate_task` with providers and models from
`orchestrator_capabilities`, preserving pstack's resolved task instructions and model
options. Set `interactionMode: "default"` when delegating execution tasks.

# Search routing

1. Check local sources first: the conversation, the repo, installed skills and connectors,
   and local tools (`--help`, installed package source). For a library question, find the
   pinned version first and research that version.
2. Search only for what local sources cannot settle, such as current releases, vendor
   docs, external errors, and prices. Memory does not settle these, even when you are
   sure. Start with the built-in web search: open the page directly when you know its
   URL.
3. Fetch and read the primary source before you state a fact: official docs, a spec, the
   upstream repo, or the vendor's own changelog, blog, release notes, or official social
   posts. A search snippet, aggregator, affiliate review, or undated post is a lead, not
   evidence.
4. Escalate to Exa when built-in search finds only snippets or secondary sources,
   cannot open the page, or returns a cached copy older than the question needs. Pick
   the Exa tool by question:
   - Vendor docs, changelogs, upstream repos: `web_search_advanced_exa` with
     `includeDomains` set to the vendor's domains.
   - Current releases, news, anything dated: `web_search_advanced_exa` with
     `startPublishedDate`.
   - Open-ended questions: `web_search_exa`.
   - Multi-hop questions: one filtered search per hop. Use `agent_run` when the list of
     entities is long or not known up front.
   If `web_search_advanced_exa` is not available, use `web_search_exa` with the vendor's
   domain or the year in the query. Read pages with `web_fetch_exa`.
   Run curl or wget on a web page only after `web_fetch_exa` failed on that page,
   truncated it, or returned a stale copy.
5. Stop once a primary source settles the question. A page that lacks the answer settles
   nothing: before you say something does not exist or was not announced, run one search
   aimed at the claim itself across the vendor's channels.
6. Put the URL beside each web-derived claim wherever it lands: the reply, a file, a PR
   body, or a report to another agent.

# Verification

- Do not add unit tests unless I explicitly request them.
- Prefer existing E2E or integration checks and verification against the real application.
- For small fixes, keep one-off verification scripts and artifacts outside the repository.
- Do not add testing frameworks, harnesses, or suites unless I explicitly request them.
- If you must test a system in isolation, first write down all the ways it could fail, then write the code.
- A test that breaks under a behavior-preserving refactor is asserting implementation, not behavior. Do not add it.
- Never delete or weaken a failing test to make the suite pass. Fix the code, or ask.

# pstack model configuration

feature, refactoring: gpt-6.1-sol
bug-fix: gpt-6.1-sol
perf-issue: gpt-6.1-sol
hillclimb: gpt-6.1-sol
judgment and prose: gpt-6.1-sol
strongest judgment: gpt-6-astra
how explorer: gpt-6.1-sol
how explainer: gpt-6.1-sol
why investigators: gpt-6.1-sol
why synthesizer: gpt-6.1-sol
reflect tooling: gpt-6.1-sol
reflect judgment, divergent, synthesizer: gpt-6.1-sol
arena runners: gpt-6-astra, gpt-6.1-sol, gpt-6-luna
arena cross-judge pool: gpt-6-astra, gpt-6.1-sol, gpt-6-luna
swarm workers: gpt-6.1-sol
architect runners: gpt-6-astra, gpt-6.1-sol, gpt-6-luna
interrogate reviewers: gpt-6-astra, gpt-6.1-sol, gpt-6-luna

default effort: session

# Google Cloud

Always prefer the installed `gcloud` CLI when interacting with Google Cloud.
Use it first for resource queries, logs, builds, and operations. Use the browser
only when the CLI cannot perform the action or when human sign-in is required.

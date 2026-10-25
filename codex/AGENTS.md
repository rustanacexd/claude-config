# Skills and task tracking

Follow a named skill's supplied instructions or read its SKILL.md and runtime mapping.
Use the current runtime's task tracker.

# Search routing

1. Check local sources first: the conversation, the repo, installed skills and connectors,
   and local tools (`--help`, installed package source). For a library question, find the
   pinned version first and research that version.
2. Search only for what local sources cannot settle, such as current releases, vendor
   docs, external errors, and prices. Memory does not settle these, even when you are
   sure. Use Exa (`web_fetch_exa` when you know the page's URL, or the search tools
   below when you don't).
3. Fetch and read the primary source before you state a fact: official docs, a spec, the
   upstream repo, or the vendor's own changelog, blog, release notes, or official social
   posts. A search snippet, aggregator, affiliate review, or undated post is a lead, not
   evidence.
4. Pick the available Exa tool by question:
   - Vendor docs, changelogs, upstream repos: `web_search_advanced_exa` with
     `includeDomains` set to the vendor's domains.
   - Current releases, news, anything dated: `web_search_advanced_exa` with
     `startPublishedDate`, plus `endPublishedDate` when the question names a closed
     period.
   - Open-ended questions: `web_search_exa`.
   - Multi-hop questions: one filtered search per hop. For a long list of entities, or
     one not known up front, use `agent_run` if available; otherwise search each hop.
   If `web_search_advanced_exa` is not available, use `web_search_exa` with the vendor's
   domain or the year in the query. Read pages with `web_fetch_exa`.
   Run `curl` or `wget` on a web page only after `web_fetch_exa` failed on that page,
   truncated it, or returned a stale copy.
5. Stop once a primary source settles the question. A page that lacks the answer settles
   nothing: before you say something does not exist or was not announced, run one search
   aimed at the claim itself across the vendor's channels.
6. Put the URL beside each web-derived claim wherever it lands: the reply, a file, a PR
   body, or a report to another agent.

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
arena runners: gpt-6-astra, gpt-6.1-sol
arena cross-judge pool: gpt-6-astra, gpt-6.1-sol
swarm workers: gpt-6.1-sol
architect runners: gpt-6-astra, gpt-6.1-sol
interrogate reviewers: gpt-6-astra, gpt-6.1-sol

default effort: session

## Strict session effort

Every pstack agent must use the calling session's current effort. This overrides
pstack's task-based effort adjustments and its instruction to omit effort for
`session`. Keep each role's configured model. Do not substitute a model default,
raise or lower effort, or reuse an effort value from an earlier turn.

The installed `pstack_effort.py` PreToolUse hook enforces this at each dispatch.
Claude Code supplies the live effort in the hook event. Codex reads the matching
current `turn_context` from the transcript and passes it as `reasoning_effort`.
If the live effort cannot be determined, the hook blocks the dispatch. Do not
bypass the hook or retry with a different effort. Report unsupported levels.

# Google Cloud

Always prefer the installed `gcloud` CLI when interacting with Google Cloud.
Use it first for resource queries, logs, builds, and operations. Use the browser
only when the CLI cannot perform the action or when human sign-in is required.

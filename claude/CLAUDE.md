# Skills and todolists

For a message starting with `/<skill>`, load that skill with the `Skill` tool unless the
harness already expanded it this turn. Reading its SKILL.md does not count as loading it.

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
     Do not load the Exa plugin's `search` skill for research; it forbids the filtered
     search.
   If `web_search_advanced_exa` is not available, use `web_search_exa` with the vendor's
   domain or the year in the query. Read pages with `web_fetch_exa`.
   Run `curl` or `wget` on a web page only after `web_fetch_exa` failed on that page,
   truncated it, or returned a stale copy.
5. Stop once a primary source settles the question. A page that lacks the answer settles
   nothing: before you say something does not exist or was not announced, run one search
   aimed at the claim itself across the vendor's channels.
6. Put the URL beside each web-derived claim wherever it lands: the reply, a file, a PR
   body, or a report to another agent.

# Stacked PRs

Build and land PR stacks with `gh stack`, never by hand. Invoke the `gh-stack` skill, or
read its SKILL.md when it is not in your invocable list. Drive it end to end. Hand back only for
my credentials, my approval of an irreversible action, or a decision no command can settle.

@~/.claude/pstack-models.md

# Google Cloud

Always prefer the installed `gcloud` CLI when interacting with Google Cloud.
Use it first for resource queries, logs, builds, and operations. Use the browser
only when the CLI cannot perform the action or when human sign-in is required.

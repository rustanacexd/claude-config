# Skills

For a message starting with `/<skill>`, load that skill with the `Skill` tool unless the
harness already expanded it this turn. Reading its SKILL.md does not count as loading it.

# Search routing

1. Check local sources first: the conversation, the repo, installed skills and connectors,
   and local tools (`--help`, installed package source). For a library question, find the
   pinned version first and research that version.
2. Search only for what local sources cannot settle, such as current releases, vendor
   docs, external errors, and prices. Memory does not settle these, even when you are
   sure. Use Exa (`web_fetch_exa` when you know the page's URL, or `web_search_exa`
   when you don't).
3. Fetch and read the primary source before you state a fact: official docs, a spec, the
   upstream repo, or the vendor's own changelog, blog, release notes, or official social
   posts. A search snippet, aggregator, affiliate review, or undated post is a lead, not
   evidence.
4. Pick the Exa tool by question:
   - Vendor docs, changelogs, upstream repos: `web_search_exa`, naming the vendor's
     domain in `objective` ("rank pages on docs.example.com first; exclude others").
   - Current releases, news, anything dated: `web_search_exa`, with the date range in
     `objective`. These are hints, not filters: check each result's domain and date
     before you rely on it.
   - Open-ended questions: `web_search_exa`.
   - Multi-hop questions: one search per hop. For a long list of entities, or one not
     known up front, use `agent_run`.
   Read pages with `web_fetch_exa`.
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

`gh stack merge` checks only that each PR is open and not a draft. It takes no head-commit
guard, and with conversation resolution required it merges nothing while any thread is open.
Right before it, read every PR's head SHA and unresolved threads; right after, read the merged
heads back and compare them with the verified SHAs. Report the window between the two.

@~/.claude/pstack-models.md

# Google Cloud

Use the installed `gcloud` CLI for Google Cloud resource queries, logs, builds, and
operations. Use the browser only when the CLI can't do the action or a human must sign in.

# Orca repo hooks

Orca reads `orca.yaml` at the repo root (`scripts.setup`, `scripts.archive`,
`setupAgentStartupPolicy`, `worktree.sharedDirectories`) and copies untracked files listed in
`.worktreeinclude`. Setup runs from the new worktree's copy; archive runs from the primary
checkout's copy, so test an unmerged archive hook in a throwaway clone, never the shared
primary checkout. `orca worktree rm` runs archive only with `--run-hooks`, and a failing archive
blocks removal. An archive script must never kill processes by command-line substring: the
Orca CLI's own argv contains the worktree path, so it kills itself (exit 143).

# Permissions for an away operator

When you send a plan for approval to someone who is not at the keyboard, list every external
write (PR thread replies or resolution, issue edits) and irreversible step (deletions) in it
that auto mode will refuse, and ask for those permissions in the same message.

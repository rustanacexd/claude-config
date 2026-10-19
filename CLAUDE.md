# Skills and todolists

For a message starting with `/<skill>`, load that skill with the `Skill` tool unless the
harness already expanded it this turn. Reading its SKILL.md does not count as loading it.

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
   docs, external errors, and prices. Use the Exa plugin's search and fetch tools. Use
   WebFetch or curl only after an Exa fetch fails, truncates, or returns a stale copy. Use
   the plugin's `search` skill only for multi-source research.
3. Fetch and read the primary source before you state a fact: official docs, a spec, the
   upstream repo, or the vendor's own changelog, blog, release notes, or official social
   posts. A search snippet, aggregator, affiliate review, or undated post is a lead, not
   evidence.
4. Stop once a primary source settles the question. A page that lacks the answer settles
   nothing: before you say something does not exist or was not announced, run one search
   aimed at the claim itself across the vendor's channels.
5. Put the URL beside each web-derived claim wherever it lands: the reply, a file, a PR
   body, or a report to another agent.

# Stacked PRs

Build and land PR stacks with `gh stack`, never by hand. Invoke the `gh-stack` skill, or
read its SKILL.md when it is not in your invocable list. Drive it end to end. Hand back only for
my credentials, my approval of an irreversible action, or a decision no command can settle.

# Testing

- Never write unit tests after you write code.
- Highly prefer E2E or integration tests as the sole testing mechanism. Use them to verify complex features work. At the end of those tests, produce a verifiable and repeatable artifact.
- If you must test a system in isolation, first write down all the ways it could fail, then write the code.
- A test that breaks under a behavior-preserving refactor is asserting implementation, not behavior. Do not add it.
- Never delete or weaken a failing test to make the suite pass. Fix the code, or ask.

# Verification

Verify the real artifact and keep evidence tied to the revision, base, scenario, and
environment it covers. Recheck applicability after changes to behavior or dependencies.
Use checks proportionate to the change; repeat them for a concrete reason, such as
instability, required sampling, or invalidated evidence. Preserve required reviews and
fresh CI. Report gaps and blockers honestly; a round limit never makes a failure a pass.
Track unrelated inherited defects separately, but block defects that defeat acceptance.

A PR's review state is what its forge shows: read its threads before calling it ready.
Name each reviewer by source, such as a delegated round or a forge bot, never by model.
A verifier's brief carries no earlier review conclusions; pass it the open threads.
After a compaction mid-playbook, re-read the playbook before the next step, not the
summary's plan.

# Delegation and shared resources

Keep each delegated task's owner, runtime, result location, and delivery state clear.
Read returned results, deliver them to the responsible owner through that runtime, and
confirm receipt or resumed work before considering the handoff complete. A completion
notice or empty process search alone does not prove an owner and its children stopped.
Give shared live-test environments and observers explicit ownership. Release your own
resources when finished; contention does not permit stopping another task's resources.

@~/.claude/pstack-models.md

# Google Cloud

Always prefer the installed `gcloud` CLI when interacting with Google Cloud.
Use it first for resource queries, logs, builds, and operations. Use the browser
only when the CLI cannot perform the action or when human sign-in is required.

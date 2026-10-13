# Skills and task tracking

Follow a named skill's supplied instructions or read its SKILL.md and runtime mapping.
Use the current runtime's task tracker. For a selected playbook, keep its numbered steps
verbatim and explicit `skip: <reason>` entries; rebuild the list after compaction or handoff.

# T3 Code only

Apply this section only when running in T3 Code.

Every pstack multi-model panel (architect runners, arena runners, the arena cross-judge
pool, interrogate reviewers, and any other model-diverse panel) has four members, in
this order: Claude Opus, Codex `gpt-6.1-sol`, Codex `gpt-6-astra`, then Claude Fable.
Run the Codex members per the pstack model configuration below. Add the Claude members
(`claude-opus-5-5` and `claude-fable-5-1`) through T3's `delegate_task`, selecting the
provider and models from `orchestrator_capabilities`. Members are added to the panel.
None replaces another, and the panel adds no rounds. Pass each `delegate_task` member
the effort that the `default effort` line resolves to, where `session` means this
session's level, because an omitted effort falls back to the provider default. If a
member's tool or model is unavailable, run the rest and name the skipped members in
the reply.

Pass `interactionMode: "default"` on every `delegate_task` call. An omitted mode
inherits this thread's, and a child in plan mode ends its turn with a proposed plan
instead of a result, where an approval step can hold it while the task reads as
running. If a delegated task has not updated in 10 minutes, read its
thread for a `proposed_plan` item or a pending request before waiting longer.

# Search routing

Answer from the repository, conversation, or installed skills first. Search the internet only when local sources cannot settle the question or the user requests current information, verification, links, or citations. Prefer the most specific available skill, connector, or repository workflow.

1. Route by question.
   - Programming documentation, APIs, SDK examples, configuration, and debugging: use the installed Exa plugin and its bundled Search skill.
   - Other web research: follow the installed Exa plugin's bundled Search skill when external research is needed.
   - Connected-service data: use the matching connector when one is available.
   - Codebase questions: use repository search and project documentation before internet search.
2. Increase depth only when the question requires it.
   - Start with 1-2 focused searches and open or fetch the strongest results.
   - For unresolved multi-hop research, follow the installed Exa plugin's research workflow and available tools.
3. For programming questions, rely on primary sources such as official documentation, specifications, and upstream repositories. For other topics, prefer authoritative sources and corroborate material claims when practical.
4. Stop when authoritative sources support the answer or when the available evidence clearly shows that the information cannot be found. Cite the supporting page URLs in the response.

# Scope and authorization

Keep one current statement of scope, acceptance criteria, and user approvals with their
message references. Reuse approvals while their scope remains the same. Preserve explicit user gates.
An agent proposal or deadline does not grant authority to merge or drop required scope.

# Verification

- Never write unit tests after you write code.
- Highly prefer E2E or integration tests as the sole testing mechanism. Use them to verify complex features work. At the end of those tests, produce a verifiable and repeatable artifact.
- If you must test a system in isolation, first write down all the ways it could fail, then write the code.
- A test that breaks under a behavior-preserving refactor is asserting implementation, not behavior. Do not add it.
- Never delete or weaken a failing test to make the suite pass. Fix the code, or ask.

Verify the real artifact and keep evidence tied to the revision, base, scenario, and
environment it covers. Recheck applicability after changes to behavior or dependencies.
Use checks proportionate to the change; repeat them for a concrete reason, such as
instability, required sampling, or invalidated evidence. Preserve required reviews and
fresh CI. Report gaps and blockers honestly; a round limit never makes a failure a pass.
Track unrelated inherited defects separately, but block defects that defeat acceptance.

# Repeated failures

When repeated fixes fail, name their shared assumption and test an observation that
could falsify it before another fix depends on it. Cite instructions or principles as
applied only after reading them in the current session.

# Delegation and shared resources

Keep each delegated task's owner, runtime, result location, and delivery state clear.
Read returned results, deliver them to the responsible owner through that runtime, and
confirm receipt or resumed work before considering the handoff complete. A completion
notice or empty process search alone does not prove an owner and its children stopped.
Do not mutate a delegated worktree until the runtime confirms its owner and children
stopped or explicitly handed it off. Use another worktree while ownership is active.
Give shared live-test environments and observers explicit ownership. Release your own
resources when finished; contention does not permit stopping another task's resources.

# pstack model configuration

feature, refactoring: gpt-6.1-sol
bug-fix: gpt-6.1-sol
perf-issue: gpt-6.1-sol
hillclimb: gpt-6.1-sol
judgment and prose: gpt-6.1-sol
strongest judgment: gpt-6.1-sol
how explorer: gpt-6.1-sol
how explainer: gpt-6.1-sol
why investigators: gpt-6.1-sol
why synthesizer: gpt-6.1-sol
reflect tooling: gpt-6.1-sol
reflect judgment, divergent, synthesizer: gpt-6.1-sol
arena runners: gpt-6.1-sol, gpt-6-astra
arena cross-judge pool: gpt-6.1-sol, gpt-6-astra
swarm workers: gpt-6.1-sol
architect runners: gpt-6.1-sol, gpt-6-astra
interrogate reviewers: gpt-6.1-sol, gpt-6-astra

default effort: session

# Google Cloud

Always prefer the installed `gcloud` CLI when interacting with Google Cloud.
Use it first for resource queries, logs, builds, and operations. Use the browser
only when the CLI cannot perform the action or when human sign-in is required.

# Skill invocation and task tracking on Codex

For a named skill, follow the supplied instructions or read its SKILL.md and Codex
mapping. Use the runtime's task tracker, such as update_plan, rather than requiring
Claude's Skill or TodoWrite tools. Keep the playbook steps and explicit skip reasons.
Cite a principle only after reading its leaf instructions in this session.

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

# Long pstack runs

Keep one current execution contract in the playbook's checkpoint and owner brief,
not another policy file. Record scope, approval message references, required review
lanes, driver scenarios, repeat counts and their reasons, and the final integrated
check and coverage gaps. Include known run costs and label estimates. Replace
superseded rules and exceptions rather than appending overrides.
An agent proposal is not user approval. A deadline does not drop required scope
or grant merge authority. Reuse approvals while their scope remains the same.

Use the selected playbook's required review lanes; do not accumulate duplicate
gates from every routed skill. Resolve conflicting requirements before dispatch.
Interrogate is for a contested design or an explicit user requirement, not an
extra routine gate. Schedule required design review before dependent work where
possible; preserve any user-specified final review. Later rounds check the fix,
its affected behavior and required gates, not the entire original review panel.
Classify findings against the base and acceptance criteria before reopening.
Track unrelated pre-existing defects separately; inherited defects that defeat
acceptance still block. At the playbook's round limit, escalate the surviving
defect with evidence. A round limit never makes a failing result acceptable.

Default to one successful run per required verification lane at the applicable head.
Repeat for changed behavior, dependencies or acceptance requirements, an invalid
receipt, observed instability, required independent proof, or performance sampling.
Record the reason before repeating. New scope needs its own review and coverage. Do not rerun a historical mutation suite for an unrelated fix.
Keep head, base, patch identity, scenario and environment with each receipt.
After a rewrite, check the new base and dependencies before retaining evidence;
an unchanged patch alone is insufficient. Required fresh CI and merge checks stay.

Review shared contracts early. Batch ready fixes before a coordinated restack,
unless a conflict or dependent task needs the new base sooner. Avoid restacking
the descendants after each review note. Final integrated driver evidence remains
required. Verify each intermediate deployment when merges auto-deploy, and include
recurring operator work in acceptance criteria. Reconcile external review threads
at the current head before declaring ready.

Refresh the active playbook and its delegated workflows when pstack changes.
Record the version and propagate changed requirements into the current owner brief.

Keep child runtime, task ID, owner ID, result location and delivery state in the
existing child ledger. When a result reaches the coordinator, read it and deliver
it to the owner through that runtime before waiting again. Record delivery and
owner acknowledgement or resumed activity. Repair missing owner IDs. Use native
status for native agents and T3 task tools for T3 tasks. A completion notice,
empty process search or quiet parent thread does not prove children stopped.
Use task or process handles for waits; do not poll with a command that matches itself.

Assign one owner and queue to each shared live-test environment and one CI observer
per PR. Record slot acquisition and release. Parallelize isolated work and release
owned resources when their run ends. Treat host contention as runtime evidence,
not permission to stop another task's resources or omit proof. When available,
the root uses T3 watch_pull_request and relays updates; otherwise use the playbook's
watcher. Do not add competing pollers or live sessions.

# Cross-model work

Codex models are one family and Claude models are another. Every pstack role runs on the
Codex models in the pstack model configuration below. Use Claude only when a pstack skill
asks for a different model family or a model-diverse panel. Architect runners, interrogate
reviewers, and arena runners and judges each include one Claude Opus 5.5 member and one
Claude Fable 5.1 member alongside the Codex models. Dispatch both through T3's
`delegate_task` with provider instance `claudeAgent`. Use model `claude-opus-5-5`
at medium effort for Opus and model `claude-fable-5-1` at medium effort for Fable.
If either Claude model is unavailable or out of credits, skip that member and continue.
If Claude is unavailable or out of credits entirely, use only `gpt-6-astra` and
`gpt-6.1-sol` for all panel work, including runners, reviewers, and judges. Single-model
roles continue on `gpt-6.1-sol`. This fallback satisfies cross-family requirements when
Claude cannot run. Do not block the workflow or keep retrying Claude after a confirmed
credit failure. Say in the reply which Claude models were skipped and that the Codex
fallback was used.

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
arena runners: gpt-6-astra, gpt-6.1-sol
arena cross-judge pool: gpt-6-astra, gpt-6.1-sol
swarm workers: gpt-6.1-sol
architect runners: gpt-6-astra, gpt-6.1-sol
interrogate reviewers: gpt-6-astra, gpt-6.1-sol

default effort: session

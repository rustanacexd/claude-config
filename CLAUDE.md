# Global instruction ownership

The `claude-config` repository owns `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`.
Before changing either file, read the repository's `README.md` and `docs/updating.md`.
Edit `CLAUDE.md` and `codex/AGENTS.md` in the repository, then run
`python3 manage.py refresh` and `python3 manage.py check-sync` from that checkout.
Do not edit the installed copies directly.

# Skills and todolists

For a message starting with `/<skill>`, load that skill with the `Skill` tool unless the
harness already expanded it this turn. Reading its SKILL.md does not count as loading it.
For a selected playbook, copy its numbered steps verbatim before task-specific items.
Keep omitted steps with `skip: <reason>` and rebuild the list after compaction or
handoff. A concise reply does not waive the steps.

# T3 Code only

Apply this section only when running in T3 Code.

Use `TodoWrite` for todolists so T3's Tasks panel can display them. If unavailable,
report the missing tool rather than silently switching to another tracker.

Every pstack multi-model panel (architect runners, arena runners, interrogate
reviewers, and any other model-diverse panel) has four members, in
this order: Claude Opus, Codex `gpt-6.1-sol`, Codex `gpt-6-astra`, then Claude Fable.
Run the Claude members with the `Agent` tool per `pstack-models.md`. Add the Codex
members through T3's `delegate_task`, selecting the provider and models from
`orchestrator_capabilities`. Members are added to the panel. None replaces another, and
the panel adds no rounds. Pass each `delegate_task` member the effort that the
`default effort` line resolves to, where `session` means this session's level, because
an omitted effort falls back to the provider default. If a member's tool or model is
unavailable, run the rest and name the skipped members in the reply.

Arena cross-judging follows pstack's default. Choose one judge from the configured
cross-judge pool. The owner reads all candidates and makes the final selection.

Pass `interactionMode: "default"` on every `delegate_task` call, because an omitted
mode inherits this thread's, and a plan-mode child cannot write files or run commands.

# Search routing

Answer from the repo, conversation, or installed skills before searching. For external
research, programming or otherwise, use the Exa plugin: start with 1-2 focused searches
with its search tool and fetch the strongest sources with its fetch tool. Invoke the
plugin's `search` skill only when the question needs multi-source research. For
programming, prefer primary sources: official docs, specs, and upstream repos. Stop once
sources support an answer or show it is unavailable, and cite the supporting URLs.

# Stacked PRs

Build and land PR stacks with `gh stack`, never by hand. Invoke the `gh-stack` skill, or
read its SKILL.md when it is not in your invocable list. Drive it end to end. Hand back only for
my credentials, my approval of an irreversible action, or a decision no command can settle.

# Never work on main

Never write on the default branch. Before the first write, run `wt switch --create
<branch>` (the `wt-switch-create` skill, or EnterWorktree when `wt` is unavailable) and
open the pull request from that branch. If the default branch has uncommitted changes you
did not make, leave them alone and report them in your first sentence.

# Delegated worktrees

A delegated worktree remains its owner's until the runtime confirms the owner and
its children have stopped or explicitly handed it off. Check for remaining processes
before mutating the checkout; an empty process search alone is not a handoff.
Use another worktree while ownership is active. Never reset another agent's database,
rebase its branch, discard its files, or commit its unfinished work.

# Scope and authorization

Keep one current statement of scope, acceptance criteria, and user approvals with their
message references. Reuse approvals while their scope remains the same. Preserve explicit user gates.
An agent proposal or deadline does not grant authority to merge or drop required scope.

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

# Repeated failures

When repeated fixes fail, name their shared assumption and test an observation that
could falsify it before another fix depends on it. Cite instructions or principles as
applied only after reading them in the current session.

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

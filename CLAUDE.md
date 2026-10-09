# Skills and todolists

For a message starting with `/<skill>`, the first tool call is `Skill` with that name.
For a selected playbook, copy its numbered steps verbatim before task-specific items.
Keep omitted steps with `skip: <reason>` and rebuild the list after compaction or
handoff. A concise reply does not waive the steps.

# T3 Code only

Apply this section only when running in T3 Code.

Use `TodoWrite` for todolists so T3's Tasks panel can display them. If unavailable,
report the missing tool rather than silently switching to another tracker.

When pstack requests a multi-reviewer or model-diverse panel, use T3's
`delegate_task` to include one Codex `gpt-6.1-sol` participant alongside Claude.
Select the provider and model from `orchestrator_capabilities`. Replace an existing
panel slot; do not add reviewers or rounds. If the tool or target model is
unavailable, report that cross-family review could not run.

# Search routing

Answer from the repo, conversation, or installed skills before searching. For external
research, programming or otherwise, use the Exa plugin: start with 1-2 focused searches
with its search tool and fetch the strongest sources with its fetch tool. Invoke the
plugin's `search` skill only when the question needs multi-source research. For
programming, prefer primary sources: official docs, specs, and upstream repos. Stop once
sources support an answer or show it is unavailable, and cite the supporting URLs.

# Stacked PRs

Build and land PR stacks with `gh stack`, never by hand, and read the `gh-stack` skill
file even when it is not in your invocable list. Drive it end to end. Hand back only for
my credentials, my approval of an irreversible action, or a decision no command can settle.

# Merging PRs

Squash-merge pull requests unless the repository disallows it.

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

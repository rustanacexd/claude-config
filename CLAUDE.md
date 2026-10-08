# Slash commands are skill invocations

A message that starts with `/<skill>` means the first tool call of that turn is `Skill`
with that exact name. Reading the skill's SKILL.md or one of its playbook files with cat
or Read is not an invocation and does not count. This holds after a context handoff,
compaction, or new session, since whatever was loaded earlier is gone. For poteto-mode
the evidence it ran is the todolist with the playbook steps copied in verbatim and a
`skip: <reason>` on every step not done, per # Todolists. No such list means the
playbook was not followed, whatever files were read. The concise output style governs the
reply, not the steps.

# Todolists

Use the `TodoWrite` tool for every todolist. Never `TaskCreate`, never a todo.md file.

When a skill or playbook defines steps, the first items of the list are those steps:

- One item per step. Copy its text from the playbook file word for word, including its number.
  Never merge steps ("1-7 ...") and never summarize or reword one.
- A step you won't do stays in the list, marked `skip: <reason>`, in exactly that form.
  Not `skip how:`, not `skip-candidate:`, not a deleted item.
- Task-specific items come after the playbook steps, never in place of them.
- Rewrite the list after a compaction or handoff. The rule still applies after either.

This applies to subagents too. A coordinator that spawns one pastes this section into the
brief, and checks the subagent's first TodoWrite before it accepts the subagent's report.

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

A delegated worktree is the subagent's until you prove it idle. A task-notification is not
proof. Run `pgrep -f <worktree path>` before writing there and stop if anything but the
search itself answers. To work while a delegate holds a worktree, use a second one. Never
reset another agent's database, rebase, `git checkout --`, or commit work you did not
write in its worktree.

# Attack the premise on the second failed round

When a review or verify gate returns findings on the same PR, file, or behaviour for a
second round, invoke `pstack:principle-attack-the-premise` with the Skill tool before
writing the next fix or brief. A verifier saying "another round would close it" counts.
Name the assumption the earlier fixes shared and the observation that could falsify it.
No further fix may rest on that assumption until the observation runs.

A coordinator writes this rule into every owner brief from round 2 onward. An owner
applies it on its own when its trail shows an earlier fix in the same area that failed
the same gate.

# Citing principles

Name a principle as applied only if you loaded its SKILL.md with the Skill tool in this
session. Briefs ask for the Skill tool, not `cat`.

# Long pstack runs

Extend the playbook's existing checkpoint and child ledger rather than making parallel
records. Keep user approvals with their original message references. Before asking again,
check that scope and authorization are still the same. Run observable comparisons before
asking for a preference or approval, while preserving explicit user gates.

Before fan-out, record required reviews, the project driver, coverage gaps, and the final
integrated-stack check. If merges auto-deploy, verify each intermediate deployment state.
Record recurring operator work in the acceptance criteria. Before declaring ready,
reconcile external review threads with their current-head dispositions. Treat a new
user requirement as a scope change, not evidence that an earlier review covered it.

When the installed pstack version changes, refresh the active playbook and the workflows
it delegates to before the next dispatch. Record the version in the checkpoint and pass
changed requirements to owners. Do not keep an old autopilot-full policy merely because
the current autopilot-stack file was read.

When a nested result reaches the coordinator, use the child ledger to deliver it to its
owner before waiting again. Record whether the child uses native agents or T3 delegation
and use that runtime's status and delivery tools. A missing owner ID is a ledger failure
to repair, not a reason to abandon the result. A completion notice or an empty process
search alone does not establish that the task and its children have stopped.

Assign one owner to each shared live-test environment and one CI observer per PR.
Parallelize isolated work. When T3's watch_pull_request is available, the root arms it
and relays check changes to owners. Otherwise use the selected playbook's watcher.
Do not run duplicate pollers or competing live sessions on the same shared environment.

# Cross-model work

Claude models are one family and Codex models are another. When a pstack skill asks for a
different model family or a model-diverse panel, include Codex. Architect runners,
interrogate reviewers, and arena runners and judges each get one Codex member alongside the
Claude models in `pstack-models.md`. Dispatch Codex through T3's `delegate_task` with
`gpt-6.1-sol` at high effort. If Codex is unavailable or out of quota, use the Claude model
the parent is not running on, and say so in the reply.

@~/.claude/pstack-models.md

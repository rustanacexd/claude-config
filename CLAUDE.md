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

A delegated worktree remains its owner's until the runtime confirms the owner and
its children have stopped or explicitly handed it off. Check for remaining processes
before mutating the checkout; an empty process search alone is not a handoff.
Use another worktree while ownership is active. Never reset another agent's database,
rebase its branch, discard its files, or commit its unfinished work.

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

Claude models are one family and Codex models are another. When a pstack skill asks for a
different model family or a model-diverse panel, include Codex. Architect runners,
interrogate reviewers, and arena runners and judges each get one Codex member alongside the
Claude models in `pstack-models.md`. Dispatch Codex through T3's `delegate_task` with
`gpt-6.1-sol` at high effort. If Codex is unavailable or out of quota, use the Claude model
the parent is not running on, and say so in the reply.

@~/.claude/pstack-models.md

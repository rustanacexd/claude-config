# Slash commands are skill invocations

A message that starts with `/<skill>` means the first tool call of that turn is `Skill`
with that exact name. Reading the skill's SKILL.md or one of its playbook files with cat
or Read is not an invocation and does not count. This holds after a context handoff,
compaction, or new session, since whatever was loaded earlier is gone. For poteto-mode
the evidence it ran is the todolist with the playbook steps copied in verbatim and a
`skip: <reason>` on every step not done. No such list means the playbook was not
followed, whatever files were read. The concise output style governs the reply, not the
steps.

# Search routing

Answer from the repo, conversation, or installed skills before searching. Programming
questions go to the `code-search-exa` skill; everything else to `WebSearch`/`WebFetch`,
falling back to `web-search-exa` when those return too little. Use `mcp__exa__agent_run`
in a subagent only after ordinary searching fails, and resume it with `runId`. Stop once
results corroborate an answer or show it is unavailable, and cite URLs.

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

# Cross-model work

Claude models are one family and Codex models are another. When a pstack skill asks for a
different model family or a model-diverse panel, include Codex. Architect runners,
interrogate reviewers, and arena runners and judges each get one Codex member alongside the
Claude models in `pstack-models.md`. The `show-me-your-work` trail review, the Eval judge,
and the Orchestrate verifier run on Codex. Dispatch Codex through T3's `delegate_task` with
`gpt-6.1-sol` at high effort. If Codex is unavailable or out of quota, use the Claude model
the parent is not running on, and say so in the reply.

@~/.claude/pstack-models.md

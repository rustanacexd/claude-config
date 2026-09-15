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

# Never work on main

Never write on the default branch. Before the first write, run `wt switch --create
<branch>` (the `wt-switch-create` skill, or EnterWorktree when `wt` is unavailable) and
open the pull request from that branch. If the default branch has uncommitted changes you
did not make, leave them alone and report them in your first sentence.

# Codex lanes

`codex-cli` is installed and working, so every `codex:*` pstack lane runs as configured.
A Claude lane is not a substitute. If a Codex lane drops out, stop the panel and report in
your first sentence: role, receipt status and error, receipt path. A sandbox denial is an
environment fault. Ask before continuing on Claude lanes only.

# Delegated worktrees

A delegated worktree is the subagent's until you prove it idle. A task-notification is not
proof. Run `pgrep -f <worktree path>` before writing there and stop if anything but the
search itself answers. To work while a delegate holds a worktree, use a second one. Never
reset another agent's database, rebase, `git checkout --`, or commit work you did not
write in its worktree.

# Artifacts

HTML artifacts are desktop only: verify at desktop width, do not test or fix mobile
rendering, keep existing responsive CSS.

Run `pstack:unslop` on written artifacts, commit messages, and pull request descriptions
before delivering them.

@~/.claude/pstack-models.md

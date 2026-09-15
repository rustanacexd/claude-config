# Search routing

Answer from the repo, conversation, or installed skills before searching, and prefer the
most specific installed skill, connector, or repo workflow. Programming questions (docs,
APIs, SDK examples, config, debugging) go to the `code-search-exa` skill; everything else
to `WebSearch`/`WebFetch`, falling back to `web-search-exa` when those return too little.

Match depth to the question: inline for a lookup, a subagent for multi-query research or
page-heavy fetching, `mcp__exa__agent_run` inside a subagent only when ordinary searching
has not settled it. Agent runs are long, so keep the run ID and resume with `runId`. Stop
once the results corroborate an answer or show the information is unavailable, and cite
URLs.

# Stacked PRs

Build and land PR stacks with the `gh stack` extension, never by hand, and read the
`gh-stack` skill file when you need its guidance. That skill not appearing in your
invocable skills does not stop you from running `gh stack` yourself. You drive it end to
end: create the branches and the PRs, set the bases, push. Hand something back only when it
genuinely needs my credentials, my approval for an irreversible action, or a decision no
command can settle.

# Never work on main

Never write on the default branch (main, master, trunk). Writing means editing, creating or
deleting a tracked file, committing, running a migration, or changing a database, container
or config the repo owns. Before the first one, run `wt switch --create <branch>` (the
`wt-switch-create` skill, or the EnterWorktree tool when `wt` is unavailable) and continue
there. Open the pull request from that branch. Reading, searching, reproducing a bug, and
drafting a plan on the default branch are fine.

If the default branch already has uncommitted changes you did not make, leave them alone
and report them in your first sentence.

# Codex lanes

`codex-cli` is installed and working, so every `codex:*` lane in a pstack panel runs as
configured. Provider diversity is what the panel is for and a Claude lane is not a
substitute. Read the `pstack:poteto-mode` skill's `references/provider-dispatch.md` before
fanning out, and dispatch each lane the way that reference specifies.

If a Codex lane drops out, stop the panel and report it in your first sentence: role,
receipt status and error, receipt path. Report a sandbox denial as an environment fault.
Ask before continuing on Claude lanes only.

# Delegated worktrees

A worktree you hand to a subagent belongs to that subagent until you prove it idle, and you
are a writer too: running something while a delegate works means a second worktree. A
task-notification is not that proof. It fires whenever an agent stops with no live
background children, it can fire more than once, and the agent resumes on its next message.
Run `pgrep -f <worktree path>` before writing in a directory you delegated, and stop if
anything but the search itself answers.

While another agent holds a worktree, never reset its database, rebase, `git checkout --`,
or commit work you did not write there. Its uncommitted changes, its branch and history,
and the databases, containers and ports its tooling owns are all its own.

# HTML artifacts

Desktop only. Verify an HTML artifact at desktop width and do not test, fix, or report on
mobile rendering; existing responsive CSS can stay.

Run `pstack:unslop` on written artifacts before delivering them, commit messages and pull
request descriptions included.

@~/.claude/pstack-models.md

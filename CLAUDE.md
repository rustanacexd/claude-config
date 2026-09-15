# Search routing
Answer from the repo, conversation, or installed skills first; search only when local sources cannot settle it. Prefer the most specific installed skill, connector, or repo workflow.

1. Route by question.
   - Programming (docs, APIs, SDK examples, config, debugging) → `code-search-exa` skill.
   - Everything else → built-in `WebSearch`/`WebFetch`; use `web-search-exa` when they fail or return too little.
2. Climb the depth ladder only as far as the question forces.
   - Inline: a quick lookup.
   - Subagent: multi-query research or page-heavy fetching. Narrow task, return short findings and source URLs.
   - `mcp__exa__agent_run` in a subagent: still unsettled after ordinary searching, or genuinely multi-hop across cross-referenced sources. Runs are long, so keep the run ID and resume with `runId`.
3. Stop when results corroborate an answer or clearly show the information is unavailable. Cite URLs.

# Stacked PRs

Build and land PR stacks with the `gh stack` extension (the `gh-stack` skill), never by hand.

# Never work on main

Do real work in a worktree on its own branch, never on the default branch
(main, master, trunk). Real work is anything that writes: editing, creating,
or deleting tracked files, committing, running a migration, or changing a
database, container, or config the repo owns. Before the first write, run
`wt switch --create <branch>` (the `wt-switch-create` skill) and continue
there. If `wt` is unavailable, use the EnterWorktree tool instead. Open the
pull request from that branch.

Preliminary investigation on the default branch is fine: reading code,
searching, running read-only commands, reproducing a bug, and drafting a
plan. The rule starts at the first write.

If the default branch already has uncommitted changes you did not make, leave
them alone and report them in the first sentence before starting.

# Codex lanes

`codex-cli` is installed and working. Every `codex:*` lane in a pstack panel runs
as configured, because provider diversity is what the panel is for; a Claude lane
is not a substitute. Under a Claude Code parent, a `codex:*` descriptor routes
through the external runner at
`skills/poteto-mode/scripts/runner/pstack-runner`, not through a native `Agent`.
The absence of a `pstack-*` agent type for Codex is not evidence the lane is
unavailable. Read `skills/poteto-mode/references/provider-dispatch.md` before
fanning out, and launch the runner with `run_in_background: true`.

If a Codex lane drops out, stop the panel and report it in the first sentence:
role, receipt status and error, receipt path. Ask before continuing on Claude
lanes only. A sandbox denial is an environment fault, not a missing model.

# Delegated worktrees

A worktree you hand to a subagent belongs to that subagent until you have
proven it idle. You are a writer too, so "give every writer its own worktree"
includes you. Needing to run something while a delegate works means making a
second worktree, not sharing one.

A task-notification saying an agent completed is not proof it is finished. It
fires whenever the agent stops with no live background children, it can fire
more than once, and the agent resumes on its next message. Before writing in a
directory you delegated, run `pgrep -f <worktree path>` and stop if anything
answers that is not the search itself.

Inside a worktree another agent is using, three things are theirs. Uncommitted
changes you did not make, including a dirty file that looks like a leftover
experiment. The checked-out branch and its history. The database, containers
and ports that worktree's tooling owns.

So while another agent holds a worktree, never reset a database, rebase,
`git checkout --`, or commit work you did not write there.

# HTML artifacts

Desktop only. When generating an HTML artifact, verify it at desktop width and
do not test, fix, or report on narrow-viewport or mobile rendering. Existing
responsive CSS can stay; it just is not something to check or spend a turn on.

Run `pstack:unslop` on written artifacts before delivering them: HTML artifacts,
documents, READMEs, RFCs, plans, commit messages, pull request descriptions, and
code comments.


@~/.claude/pstack-models.md

# Workflow gates

The gates are Claude Code hooks. Each one checks the session for workflow
evidence at one point:

- G1 refuses `gh pr merge` and `gh stack merge`.
- G2 refuses `gh pr create` and `gh stack submit` until deslop and no-comments
  ran, and refuses a `git commit` or `git push` that skips the git hooks.
- G3 refuses to end a poteto-mode turn that has no todolist, cites a principle
  it did not read, or changed code without a later advisor call.
- G6 refuses `gh pr create` and `gh stack submit` on a diff of more than one
  file when poteto-mode is not active.
- G7 never refuses anything. After a compaction in a poteto-mode session, it
  gives the model back the playbooks it read, its open tasks and its skips.

## Install the gates in warn mode

Add these entries to `~/.claude/settings.json`, then run `./refresh.sh` so
that `~/.claude/gates` links to this directory:

```json
"hooks": {
	"PreToolUse": [
		{
			"matcher": "Bash",
			"hooks": [
				{
					"type": "command",
					"command": "GATES_MODE=warn $HOME/.claude/gates/gate.sh PreToolUse Bash",
					"timeout": 60
				}
			]
		}
	],
	"Stop": [
		{
			"hooks": [
				{
					"type": "command",
					"command": "GATES_MODE=warn $HOME/.claude/gates/gate.sh Stop",
					"timeout": 10
				}
			]
		}
	],
	"SessionStart": [
		{
			"matcher": "compact",
			"hooks": [
				{
					"type": "command",
					"command": "GATES_MODE=warn $HOME/.claude/gates/gate.sh SessionStart compact",
					"timeout": 10
				}
			]
		}
	]
}
```

Keep `GATES_MODE=warn` in the command. A bare script path installs block mode.

To turn every gate off, run `touch ~/.claude/gates.off`. While that file
exists, `gate.sh` exits 0 on every event before it reads its input, and
Python never starts. To turn the gates on again, run
`rm ~/.claude/gates.off`. The file sits outside the repo, so it cannot be
committed through the `~/.claude/gates` symlink.

`gate.sh` takes the hook event as its first argument. With `PreToolUse Bash`,
it starts Python only when the command contains a trigger literal of a Bash
gate. Every other event starts Python on every call. Give an entry for `Stop`
or `SessionStart` a `timeout` of 10, and an entry for `PreToolUse` or
`TaskCompleted` a `timeout` of 60. The gates stop themselves at 7 and 40
seconds, because a hook that times out allows the call.

## Switch from warn to block

`GATES_MODE` selects the mode for every gate. `GATES_MODE_<gate>`, for example
`GATES_MODE_G6=warn`, overrides it for one gate.

- With `warn`, the call runs, and the findings start with `This was NOT
  blocked, because the gate is in warn mode`. On `PreToolUse` and
  `SessionStart` the model receives them. On `Stop` and `TaskCompleted` only
  the user sees them.
- With any other value, or none, the hook exits 2, and the call does not run.
  The model receives the findings on stderr.

To block, change the command to
`GATES_MODE=block $HOME/.claude/gates/gate.sh PreToolUse Bash`. Set
`GATES_LOG=<path>` in the command to append one JSON line per decision,
including the Python version that ran it.

An advisory requirement never blocks in any mode. Its failure is a line that
starts with `ADVISORY`, and it goes where the table below sends a warning.

## How each event reports

Claude Code shows `additionalContext` and stderr to the model, and
`systemMessage` to the user only.

| Event | Block | Warning, advisory, or skip note | Gate crash |
| --- | --- | --- | --- |
| `PreToolUse` | exit 2, stderr, to the model | exit 0, `additionalContext`, to the model | blocks |
| `TaskCompleted` | exit 2, stderr, to the model | exit 0, `systemMessage`, to the user | blocks |
| `Stop` | exit 2, stderr, to the model | exit 0, `systemMessage`, to the user | allows, with `systemMessage` to the user |
| `SessionStart` | never blocks | exit 0, `additionalContext`, to the model | allows, with `systemMessage` to the user |

TaskCompleted has no `additionalContext`. Stop accepts `additionalContext` too, but Claude Code then keeps the turn
going, the same as a block. A warning on Stop therefore uses `systemMessage`.
Claude Code shows that message to the user and does not send it to the model,
in this turn or the next. In warn mode, G3 reports to the user only.

A crash on Stop or SessionStart allows the call, because a Stop gate that
always crashed would keep every session from ending. So does a transcript the
gate cannot read, a missing `hook.py`, and a check that raises an error. On
`PreToolUse` and `TaskCompleted` each of these blocks.

After a Stop hook blocks, Claude Code continues the turn and sends the next
Stop with `stop_hook_active` set. The gates never block that Stop. They report
what still fails through `systemMessage` and let the turn end, so a gate
blocks a turn at most once. Claude Code also stops honoring blocks after
eight in a row, but the gates do not rely on that limit.

## What G1 checks

G1 runs on a Bash command that contains the literal `gh pr merge` or
`gh stack merge`. It parses the command, so a merge inside a heredoc, a quoted
string, or a `grep` pattern does not count. Each real `gh pr merge` must pass
all six requirements:

| Requirement | Passes when |
| --- | --- |
| `G1.R1` | The latest comment that names the PR's current head (8 or more hex characters) and contains `PASS`, `PASS+NOTES` or `FAIL` says `PASS` or `PASS+NOTES`. Comments this session posted do not count. G1 recognizes them by the comment id the post printed. If a post printed no id, for example because its output went to `/dev/null`, G1 also excludes every comment on that PR created between 5 seconds before the post started and 5 seconds after it finished. |
| `G1.R2` | The command passes `--match-head-commit` with a literal 40-character SHA equal to the PR's current head. |
| `G1.R3` | G1 sorts the comments this session did not post into three kinds: conversation comments, review bodies, and diff-line comments. For each kind that has any, a successful read of that kind started at least one second after the newest change to those comments. |
| `G1.R4` | The acting agent called `advisor` after the last push by the main thread or by itself. A push is `git push` or `gh stack push`, `submit` or `sync`. |
| `G1.R5` | The acting agent read `playbooks/shipping.md` in full after its own last compaction. A plain `cat` or `Read` counts. So does any other read, such as `sed -n 1,80p` or `cat \| head -60`, whose output shows every non-blank line of the file as it is on disk now. |
| `G1.R6` | A user message contains `merge`, `land` or `ship`, and the words before it hold no negation such as `don't` or `not yet`. Text the harness adds to a message, such as system reminders, task notifications and slash-command wrappers, does not count. |

The block message lists every requirement, each with its result and the
command or file that would satisfy it. G1 gets PR facts from `gh pr view` and
`gh api`. If `gh` fails, R1, R2 and R3 fail with the reason, and R4, R5 and
R6 still report. If G1 cannot read the transcript, every requirement except
R2 fails.

Inside a subagent, the evidence for R3, R4 and R5 must be in that subagent's
own transcript. User messages come from the main session.

### Stack merges

`gh stack merge <pr>` merges that PR and every unmerged PR below it, and
`gh stack merge` with no target merges the whole stack. G1 reads the set from
`gh stack view --json` in the command's working directory and checks every PR
in it against R1 to R6.

`gh stack merge` has no `--match-head-commit`, so R2 changes for a stack
merge. It passes when a verdict comment on the PR names the PR's current head.

G1 blocks the stack merge, with a remedy, when it cannot resolve the set:

- The target is not a literal number.
- The target is not an unmerged PR of the stack checked out in the working
  directory. `gh` reads a bare number as a stack number first, and
  `gh stack view` cannot name stacks, so G1 accepts only PR numbers.
- `gh stack view --json` fails.

## What G2 checks

G2 runs on `gh pr create`, `gh stack submit`, `git commit` and `git push`.
R1, R2 and R3 apply at `gh pr create` and `gh stack submit`, and only when
poteto-mode is active. R4 applies in every session.

| Requirement | Passes when |
| --- | --- |
| `G2.R1` | The session ran the `deslop` skill after its last edit. |
| `G2.R2` | The session ran the `no-comments` skill after its last edit. |
| `G2.R3` | Advisory. The session ran, or read in full, both `technical-writing` and `unslop`. |
| `G2.R4` | The command does not skip the git hooks with `--no-verify` or a prefix of it such as `--no-veri`, with `-n` on `git commit`, or with a `core.hooksPath` override through `-c` or `--config-env`. |

An edit is an `Edit`, `Write`, `MultiEdit` or `NotebookEdit` call that did not
fail, or a Bash command that writes a file with `>`, `>>`, `tee`, `sed -i` or
`perl -i` and did not exit with an error. A command whose result has not
arrived yet counts. A write to `/dev/` is not an edit. G2 looks for edits and skill runs in the main transcript and in every
subagent transcript. Within one file it orders them by line, and across files
by timestamp. With no edit in the session, R1 and R2 pass.

poteto-mode is active when the main session or the acting subagent ran the
`poteto-mode` skill, or when the acting subagent's type starts with
`pstack:poteto-agent`. A skill run is a `Skill` call or a slash command the
user typed. `pstack:deslop`, `/pstack:deslop` and `deslop` name the same
skill.

## What G3 checks

G3 runs when the main agent ends a turn in a poteto-mode session. A subagent's
turn ends through `SubagentStop`, which G3 does not handle. A turn is
everything after the last message the user typed. Messages that Claude Code
adds, such as Stop hook feedback and task notifications, do not start a turn.

| Requirement | Passes when |
| --- | --- |
| `G3.R1` | A task change (`TaskCreate`, `TaskUpdate`, `TodoWrite`) or a write to a `*todo*.md` file, from an edit tool or from Bash, follows the last `poteto-mode` run. The main transcript and every subagent transcript count. |
| `G3.R2` | Advisory. For each poteto-mode playbook read in full after the first `poteto-mode` run, every numbered step appears in the task and todo text. G3 compares the first 40 characters of each step, in lower case, without `*` or backticks. A todo line that holds `skip:` and the step's number also covers the step. |
| `G3.R3` | Every principle that the final reply names, by its display name or its slug, was read in full or run as a skill in this session. G3 reads the names from the Principles index of the poteto-mode `SKILL.md` that the session read, or else from the newest one in the plugin cache. |
| `G3.R4` | If this turn edited, committed or pushed, an `advisor` call follows the last of those changes. Changes in subagent transcripts count. |
| `G3.R5` | Advisory. If the final reply says `done`, `fixed`, `merged`, `landed`, `complete` or `ready for review` without a negation just before it, no edit in this turn follows the turn's last test run. |
| `G3.R6` | Advisory. Every app session brought up with `npm run e2e:control -- up` was later brought down with `down`. `APP_SCRIPTS` in `evidence.py` lists the scripts and their verbs. |

R1, R3 and R4 block. G3 reads the final reply from `last_assistant_message`,
because the transcript can lag it.

## What G6 checks

G6 runs on `gh pr create` and `gh stack submit` in every session.

| Requirement | Passes when |
| --- | --- |
| `G6.R1` | poteto-mode is active, or the branch diff touches at most one file. |

G6 counts the files with `git diff --name-only origin/<base>...<head>` in the
command's working directory, and falls back to `<base>...<head>` when the
remote branch is missing. The base is `--base`, else the remote default
branch, else `main`. The head is `--head`, else `HEAD`. If `git` fails, R1
fails. Inside a subagent, a `poteto-mode` run in the main session counts.

## What G7 adds after a compaction

G7 runs on `SessionStart` with the `compact` source in a poteto-mode session.
It never blocks. It returns `additionalContext` of at most 2,000 characters
with these items:

- A line that tells the model to re-read each playbook in full, and that G1
  accepts only a full read of `playbooks/shipping.md` made after the
  compaction.
- The paths of the poteto-mode playbooks the session read.
- The open tasks. A task is open until a `TaskUpdate` marks it `completed` or
  `deleted`. For `TodoWrite`, G7 lists the open items of the last call.
- The `*todo*.md` files the session wrote.
- Each task or todo line that contains `skip:`.

When the text is longer than 2,000 characters, G7 cuts the last lines and ends
with `cut at 2000 characters`.

## Skip a requirement

To skip a requirement you cannot meet, write this line in a task (`TaskCreate`
or `TaskUpdate`) or in a `*todo*.md` file:

```text
skip: G2.R4 the hook needs a network the sandbox lacks
```

A todo file written from Bash, for example through a heredoc, leaves no text
in the transcript, so the gates read its lines from the file when they run.

The reason is required. The allowed call echoes each skip and its reason as
a note, through the channel the table in "How each event reports" names.

Claude Code sometimes writes a tool call to the transcript after the next
call's hook has already run. A skip declared in the call just before can then
be missing, and the block message says to run the command again.

`G1.R6` and `G6.R1` cannot be skipped. If the user authorized landing in
words G1 does not recognize, ask them to say `merge`, `land` or `ship`. For
`G6.R1`, run the poteto-mode skill.

## Where the gates differ from the written spec

- **G1.R2 requires all 40 characters.** The spec says the pin must equal the
  head, and a prefix does not equal it. A shell variable such as `$H` fails,
  because its value is unknown until the shell runs.
- **G1.R6 cannot be skipped, and only the user can satisfy it.** A
  `skip: G1.R6` line or a `land authorized:` quote would be written by the
  model, so it would be the model authorizing itself. G1 ignores both. To
  restore the spec's skip, set `escapable=True` on `R6` in `g1_merge.py`.
- **G6.R1 cannot be skipped.** The spec lets a `skip:` line waive any
  requirement. G6.R1 exists to make the model follow poteto-mode, and the
  model writes the skip lines, so a skip would be the model waiving its own
  mandate. G6 ignores a `skip: G6.R1` line. To restore the spec's skip, set
  `escapable=True` on `R1` in `g6_mandate.py`.
- **G1.R3 checks each kind of comment against its latest change.** The spec
  compares one read against the newest comment's creation time. G1 compares
  each kind separately and uses the later of the creation and update times,
  because an in-place edit, such as a rewritten bot summary, is new
  information. A `--jq` filter that prints less than every comment still
  counts as a read.
- **G2.R1 and G2.R2 restart at an edit, not at a commit.** The spec restarts
  them at the last edit or commit. poteto-mode runs deslop before a commit, so
  the usual order is edit, deslop, commit, then open the PR, and a commit adds
  no code that an edit did not add. A file written from Bash counts as an
  edit instead, which closes the path where a Bash write and a commit after
  deslop reached the PR unreviewed. Across 213 PR opens in past poteto
  sessions, a commit restart failed 211, and the edit restart with Bash writes
  failed 177. Of the 71 opens that the Bash writes added, 57 changed source,
  tests, config or docs after deslop.
- **G2.R1 and G2.R2 ignore scratch files.** A scratch file sits under `/tmp`
  or another temp directory and outside any git work tree, such as a PR body
  written for `gh pr create --body-file`. An edit in a git work tree under
  `/tmp` still counts.
- **G2.R1 and G2.R2 ignore `*todo*.md` files.** poteto-mode keeps its
  checklist in a `todo.md` when no task tool exists, and ticking an item after
  deslop changes no code.
- **G6 checks poteto-mode before it runs `git`.** The spec counts the files
  first. The verdict is the same whenever `git` works, and a poteto session no
  longer fails when `git` cannot answer.
- **G3.R3 counts a skill run as a read.** The Skill tool loads the same
  `SKILL.md` that a Read would.
- **G3.R4 and G3.R5 ignore scratch files and `*todo*.md` files,** for the
  reasons given for G2.R1 above.
- **G3.R6 keeps its commands in `evidence.py`.** The spec reads them from a
  project's verification skill at run time. That path names a private
  project, and the commands are the same generic `npm run e2e:control` verbs.
- **G7 names only G1 in its re-read line.** The spec says G1 and G2 require
  the re-read. G2 does not check playbook reads.
- **Stop reports a warning through `systemMessage`.** The spec's amendment
  asks for `additionalContext`, but on Stop that keeps the conversation going,
  so a warn-mode gate would hold every turn open. The cost is that the model
  does not see the warning; only the user does.
- **Block is the default.** An unset `GATES_MODE` blocks. The install snippet
  sets `warn` explicitly.

## Limits

- The parser does not follow a command into another program. It misses a
  script piped into a shell (`echo 'gh pr merge 1' | bash`), process
  substitution (`bash <(...)`), a `function f { ...; }` body, and a command
  held in a variable (`c='gh pr merge 1'; $c`).
- A word that references a variable is a shell expression, unless the same
  command line assigned that variable earlier with a literal value, as in
  `P=~/x; cat $P/f`. Then the word carries the value. A variable assigned in
  an earlier Bash call, or from a command substitution, is not substituted.
- `gate.sh` starts Python for a Bash command only when the command contains
  `gh pr merge`, `gh stack merge`, `gh pr create`, `gh stack submit`,
  `git commit`, `git push` or `--no-verify`, or contains `git -` followed
  later by ` commit` or ` push`. A call spelled another way passes unchecked,
  for example with two spaces, as `gh api -X PUT .../merge`, or from inside
  `python -c`.
- G2.R4 sees a `core.hooksPath` override only on the command line. It misses
  one set through `GIT_CONFIG_COUNT` or `GIT_CONFIG_PARAMETERS`, one written
  earlier with `git config`, and a `-c` whose setting is a shell variable.
- Once `gate.sh` starts, any failure on `PreToolUse` or `TaskCompleted`
  blocks. Every non-zero exit from Python becomes exit 2, and so does a
  missing `python3`. A missing `gate.sh` exits 127, which Claude Code does not
  treat as a block, so the call runs.
- G2 sees a Bash write only through `>`, `>>`, `tee`, `sed -i` and `perl -i`.
  It misses `cp`, `mv`, `patch`, `git apply`, `dd`, `install`, `rsync`,
  `truncate`, `git checkout <rev> -- <path>`, `gsed -i`, a `sed -i` run by
  `xargs` or `find -exec`, a redirect with no command such as `> file`, a
  script that writes files, and a redirect to a path held in a shell variable.
  A write to a decision log in the repo, such as `.audit/log.tsv`, counts as an
  edit.
- G3.R6 misses a `down` that runs inside a script file, for example a
  heredoc written to `run.sh` and then run with `bash run.sh`.
- G3 reads a `*todo*.md` file that Bash wrote from disk when the turn ends,
  so a tick or a skip line added to the file later counts. A file moved or
  deleted before the turn ends still satisfies R1, because the transcript
  holds the write, but its skip lines are gone. A write from an edit tool
  keeps its content in the transcript.
- G3.R2 checks the steps of a playbook only after a complete read of it. A
  playbook read with `head`, `sed -n`, a piped `cat`, or `Read` with an
  offset or limit is not checked.
- G3.R4 and G3.R5 do not count a write to a scratch file or a `*todo*.md`
  file, so such a write after the advisor call, or after the last test run,
  passes.
- G3.R6 looks at the newest `up` only. A `down` before it does not count, and
  an earlier `up` of the same app that never came down passes once a later
  `up` has its `down`.
- G7 lists the items of the last `TodoWrite` call only. An item that an
  earlier call held and the last call dropped is not restored.

## Layout and tests

- `gate.sh` is the shell entry point that every hook command runs.
- `hook.py` reads the hook payload, picks the gates registered for its event
  and tool, runs them, and exits 0 or 2. A gate's `trigger_literals` are shell
  `case` patterns: `gate.sh` and `hook.py` both match each as `*<pattern>*`,
  and a test checks that the two lists agree.
- `core.py` defines events, requirements, escapes and decisions, and renders
  the hook output for each event.
- `evidence.py` parses shell commands and transcripts. Its classifier table is
  the one definition of a push, a comment read, a comment post, a file read,
  a file write, a commit and a test run. It also records skill runs, agent spawns, edits and
  task changes.
- `github.py` reads PR facts and stack membership through `gh`.
- `g1_merge.py`, `g2_pr.py`, `g3_stop.py` and `g6_mandate.py` hold each
  gate's requirements. `g7_compact.py` builds the text that G7 returns.

Run the tests from the repo root:

```sh
python3 -m unittest discover -s tests
```

`tests/test_replay_local.py` replays real sessions from a machine-local case
table. It skips unless `~/.local/share/claude-gates/replay/cases.json`
exists.

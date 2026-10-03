# Workflow gates

The gates are Claude Code hooks. Each one refuses a tool call until the session
shows the workflow evidence for it. G1 is the first gate, and it refuses
`gh pr merge`.

## Install G1 in warn mode

Add this entry to `~/.claude/settings.json`, then run `./refresh.sh` so that
`~/.claude/gates` links to this directory:

```json
"hooks": {
	"PreToolUse": [
		{
			"matcher": "Bash",
			"hooks": [
				{
					"type": "command",
					"command": "GATES_MODE=warn $HOME/.claude/gates/g1.sh",
					"timeout": 60
				}
			]
		}
	]
}
```

Keep `GATES_MODE=warn` in the command. A bare script path installs block mode.

## Switch from warn to block

`GATES_MODE` selects the mode:

- With `warn`, the merge runs. The model receives the findings as
  `additionalContext` that starts with `GATES_MODE=warn, so this was NOT
  blocked`.
- With any other value, or none, the hook exits 2, and the merge does not run.
  The model receives the findings on stderr.

To block, change the command to `GATES_MODE=block $HOME/.claude/gates/g1.sh`.
Set `GATES_LOG=<path>` in the command to append one JSON line per merge
decision, including the Python version that ran it.

## What G1 checks

G1 runs on a Bash command that contains the literal `gh pr merge`. It parses
the command, so a merge inside a heredoc, a quoted string, or a `grep` pattern
does not count. Each real `gh pr merge` must pass all six requirements:

| Requirement | Passes when |
| --- | --- |
| `G1.R1` | The latest comment that names the PR's current head (8 or more hex characters) and contains `PASS`, `PASS+NOTES` or `FAIL` says `PASS` or `PASS+NOTES`. Comments this session posted do not count. G1 recognizes them by the comment id the post printed. If a post printed no id, for example because its output went to `/dev/null`, G1 also excludes every comment on that PR created between 5 seconds before the post started and 5 seconds after it finished. |
| `G1.R2` | The command passes `--match-head-commit` with a literal 40-character SHA equal to the PR's current head. |
| `G1.R3` | G1 sorts the comments this session did not post into three kinds: conversation comments, review bodies, and diff-line comments. For each kind that has any, a successful read of that kind started at least one second after the newest change to those comments. |
| `G1.R4` | The acting agent called `advisor` after the last push by the main thread or by itself. A push is `git push` or `gh stack push`, `submit` or `sync`. |
| `G1.R5` | The acting agent read `playbooks/shipping.md` in full after its own last compaction. A `Read` with `offset` or `limit` and a `cat` piped into another command are partial reads. |
| `G1.R6` | A user message contains `merge`, `land` or `ship`, and the words before it hold no negation such as `don't` or `not yet`. Text the harness adds to a message, such as system reminders, task notifications and slash-command wrappers, does not count. |

The block message lists every requirement, each with its result and the
command or file that would satisfy it. G1 gets PR facts from `gh pr view` and
`gh api`. If `gh` fails, R1, R2 and R3 fail with the reason, and R4, R5 and
R6 still report. If G1 cannot read the transcript, every requirement except
R2 fails.

Inside a subagent, the evidence for R3, R4 and R5 must be in that subagent's
own transcript. User messages come from the main session.

## Skip a requirement

To skip a requirement you cannot meet, write this line in a task (`TaskCreate`
or `TaskUpdate`) or in a `*todo*.md` file:

```text
skip: G1.R4 the advisor is down and the user knows
```

The reason is required. The allowed merge echoes each skip and its reason
through `additionalContext`, so the skip shows in the transcript.

`G1.R6` cannot be skipped. If the user authorized landing in words G1 does not
recognize, ask them to say `merge`, `land` or `ship`.

## Where G1 differs from the written spec

- **R2 requires all 40 characters.** The spec says the pin must equal the
  head, and a prefix does not equal it. A shell variable such as `$H` fails,
  because its value is unknown until the shell runs.
- **R6 cannot be skipped, and only the user can satisfy it.** A `skip: G1.R6`
  line or a `land authorized:` quote would be written by the model, so it would
  be the model authorizing itself. G1 ignores both. To restore the spec's skip,
  set `escapable=True` on `R6` in `g1_merge.py`.
- **R3 checks each kind of comment against its latest change.** The spec
  compares one read against the newest comment's creation time. G1 compares
  each kind separately and uses the later of the creation and update times, because an in-place edit,
  such as a rewritten bot summary, is new information. A `--jq` filter that
  prints less than every comment still counts as a read.
- **Block is the default.** An unset `GATES_MODE` blocks. The install snippet
  sets `warn` explicitly.

## Limits

- The parser does not follow a command into another program. It misses a
  script piped into a shell (`echo 'gh pr merge 1' | bash`), process
  substitution (`bash <(...)`), a `function f { ...; }` body, and a command
  held in a variable (`c='gh pr merge 1'; $c`).
- `g1.sh` runs Python only when the command contains the exact text
  `gh pr merge`. A merge spelled another way passes unchecked, for example
  with two spaces, or as `gh api -X PUT .../merge`, or from inside
  `python -c`.
- Once `g1.sh` starts, any failure blocks. Every non-zero exit from Python
  becomes exit 2, and so does a missing `python3`. A missing `g1.sh` exits 127,
  which Claude Code does not treat as a block, so the merge runs.

## Layout and tests

- `g1.sh` is the shell entry point that the hook command runs.
- `hook.py` reads the hook payload, runs the gates, and exits 0 or 2.
- `core.py` defines requirements, escapes and decisions, and renders the
  hook output.
- `evidence.py` parses shell commands and transcripts. Its classifier table is
  the one definition of a push, a comment read, a comment post, a file read
  and a commit.
- `github.py` reads PR facts through `gh`.
- `g1_merge.py` holds the six requirements.

Run the tests from the repo root:

```sh
python3 -m unittest discover -s tests
```

`tests/test_replay_local.py` replays real merges from a machine-local case
table. It skips unless `~/.local/share/claude-gates/replay/cases.json`
exists.

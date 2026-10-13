# Install third-party skills

For a new machine, ask the setup agent to run the commands below after `python3 manage.py bootstrap`. Install Node/npm and Git first. These commands require network access and use the [Vercel Skills CLI](https://github.com/vercel-labs/skills).

Install the listed skills globally for both Claude Code and Codex. `--copy` creates regular files. The CLI owns their locations, tracking, and updates. Currently Claude skills go under `~/.claude/skills`, and Codex skills go under `~/.agents/skills`. Custom home overrides for this repository's Python installer do not redirect these global CLI commands. Use an isolated OS home when testing them.

```sh
npx skills add vercel-labs/skills --skill find-skills -g -a claude-code codex --copy -y
npx skills add google/skills --skill finding-google-skills gcloud -g -a claude-code codex --copy -y
npx skills add cli/cli --skill gh -g -a claude-code codex --copy -y
npx skills add github/gh-stack --skill gh-stack -g -a claude-code codex --copy -y
npx skills add shadcn/improve --skill improve -g -a claude-code codex --copy -y
npx skills add backnotprop/bro --skill status -g -a claude-code codex --copy -y
npx skills add backnotprop/plannotator/apps/skills/core --skill plannotator plannotator-annotate plannotator-last plannotator-review -g -a claude-code codex --copy -y
npx skills add getsentry/sentry-for-ai --skill sentry-create-alert sentry-debug-issue sentry-fix-stack-traces sentry-get-started sentry-instrument sentry-otel-exporter-setup sentry-setup-releases sentry-snapshots-cocoa -g -a claude-code codex --copy -y
```

After installation, inspect the native CLI inventory.

```sh
npx skills list -g -a claude-code codex
```

For updates, run `npx skills update -g` and review the results. Skill versions follow upstream repositories. This list does not pin their contents.

The repository's `manage.py refresh` installs the shared `show-me` and `explain-diff-html` skills and eight Codex-only Visual Explainer shortcuts. Native plugins, including pstack, supply their own skills through each app's plugin manager. Leave those with their plugins.

## Install Visual Explainer

Claude Code uses the [upstream marketplace plugin](https://github.com/nicobailon/visual-explainer#install), declared in `plugins.json`. Restore it with `python3 manage.py bootstrap --app claude`, or install it directly:

```sh
claude plugin marketplace add nicobailon/visual-explainer --scope user
claude plugin install visual-explainer@visual-explainer-marketplace --scope user
```

For Codex, install the upstream skill with the same Skills CLI used above:

```sh
npx skills add nicobailon/visual-explainer --skill visual-explainer -g -a codex --copy -y
python3 manage.py refresh --app codex
```

The Skills CLI installs upstream resources under `~/.agents/skills/visual-explainer`. Refresh installs this repository's shortcuts under the selected Codex home's `skills` directory. They also support the upstream guide's `~/.codex/skills/visual-explainer` location. The repository stores only the shortcuts, not upstream resources.

Start a new session to load the commands. In Claude Code, use `/visual-explainer:diff-review`. In Codex, type `$visual-explainer-` to select `diff-review`, `fact-check`, `generate-slides`, `generate-video`, `generate-visual-plan`, `generate-web-diagram`, `plan-review`, or `project-recap`.

Basic HTML generation needs a browser. Video and PowerPoint export have optional dependencies described in the upstream guide.

Some listed skills need additional tools such as `gh`, `gcloud`, Plannotator, or Bash. Install those tools before using the corresponding skill.

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

The repository's `manage.py refresh` installs only its custom `show-me` and `explain-diff-html` skills. Native plugins, including pstack, supply their own skills through each app's plugin manager. Leave those with their plugins.

Some listed skills need additional tools such as `gh`, `gcloud`, Plannotator, or Bash. Install those tools before using the corresponding skill.

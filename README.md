# Portable Claude and Codex setup

Shared Claude Code and Codex configuration for macOS, Linux, and Windows.

This repository keeps global instructions, separate pstack model sheets, settings, output styles, two custom skills, and plugin declarations. Third-party skills are listed in [SKILLS.md](SKILLS.md) and installed through `npx skills`.

Python 3.11 or newer applies shared defaults as regular files. Offline refresh needs no Bash, jq, Node, or symlink privileges. Native plugins and third-party skills use their own installers. Credentials and account connections stay on each machine.

## Start with the matching guide

- [Set up a machine](docs/setup.md) covers prerequisites, bootstrap, authentication, and the complete setup-agent checklist.
- [Update machines](docs/updating.md) covers the Mac, GitHub, and Windows flow, shared source files, local edits, skills, and plugins.
- [Recover an installation](docs/recovery.md) covers ownership, private state, backups, interrupted writes, and legacy migration.
- [Verify the portable setup](docs/testing.md) covers tests, isolated refresh, and the limits of machine-verification claims.
- [Install third-party skills](SKILLS.md) lists upstream sources and the exact install commands.

## Apply shared changes

After pulling repository changes, run this from the checkout on macOS or Linux.

```sh
python3 manage.py refresh
```

On Windows use `py -3 manage.py refresh`, or `python manage.py refresh` if `py` is unavailable.

Refresh preserves local changes and does not publish installed-file edits back to GitHub. Follow [Update machines](docs/updating.md) for skill and plugin changes.

A setup agent must read [Set up a machine](docs/setup.md) and [SKILLS.md](SKILLS.md) before changing a machine. Report actual machine results separately from CI results.

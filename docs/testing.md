# Verify the portable setup

Run these checks from the repository checkout. Use isolated app homes for installer tests. Global `npx skills` commands need an isolated OS home because the Python installer's `--home` does not redirect them.

## Run the automated suite

```sh
python3 -m unittest discover -s tests -v
```

Tests use synthetic configs and temporary homes, including paths with spaces. They exercise the actual CLI, repeated refresh, local edits and deletions, nested skill resources, native JSON variations, secret canaries, foreign links, interrupted publication and conflict refusal. GitHub Actions runs Python 3.11 and 3.13 on Ubuntu, macOS and Windows. Symlink fixture tests may skip when the runner cannot create a fixture; ordinary installation still runs without links.

On Windows use `py -3 -m unittest discover -s tests -v`, or `python -m unittest discover -s tests -v` if the launcher is unavailable.

## Check refresh in temporary homes

Use a fresh directory outside the repository for `--home`.

```sh
python3 manage.py refresh --home /path/to/temporary-home
python3 manage.py refresh --home /path/to/temporary-home
```

The first command creates `claude` and `codex` homes inside that directory. The second reports zero changes if the source and installed files have not changed. Confirm that each app has its own global instructions, model sheet, and two custom skills. Refresh stays offline and does not install native plugins or third-party skills.

## Report machine verification separately from CI

For a complete machine run, follow the [setup-agent checklist](setup.md#follow-the-setup-agent-checklist). Verify native plugin inventory, upstream skills, launchers, global instructions, distinct model sheets, and repeated refresh. Record the checkout revision, OS, commands, and observed results. List pending authentication and unsupported capabilities separately from command failures.

A successful Windows CI run does not establish that a run succeeded on the user's connected Windows machine. The same distinction applies to macOS and Linux.

PR #19's Windows verification at `7b0d60d` ran on the connected Windows machine. It reported 41 tests passed without skips, installation of all 19 upstream skills and 9 native plugins, launcher and Sentry startup checks, and zero changes on repeated refresh. That run used elevated privileges. Account authentication remained pending, and background cache metadata changed. These results do not establish ordinary-user ACL behavior or complete isolation of every real-home file.

Later changes need their own verification. Keep the reported revision with the results rather than treating this historical run as proof of the current checkout.

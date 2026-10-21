---
name: visual-explainer-compare
description: "Compare two or more options side by side, recommend one, and let the reader pick in the page, using the visual-explainer workflow."
---

Locate the installed `visual-explainer/SKILL.md` under `$CODEX_HOME/skills` (default `~/.codex/skills`) or `~/.agents/skills`. Read and follow it, then read `commands/compare.md` inside that same skill directory. If the upstream skill is missing, install it with `npx skills add nicobailon/visual-explainer --skill visual-explainer -g -a codex --copy -y` before continuing.

Interpret the workflow's `$@` placeholder as the user's arguments or request accompanying this invocation. Resolve its relative references, templates, and scripts from the upstream skill directory. Preserve the workflow's defaults and input requirements.

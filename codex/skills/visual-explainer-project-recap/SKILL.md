---
name: visual-explainer-project-recap
description: "Generate a visual project recap for context switching using the visual-explainer workflow."
---

Locate the installed `visual-explainer/SKILL.md` under `$CODEX_HOME/skills` (default `~/.codex/skills`) or `~/.agents/skills`. Read and follow it, then read `commands/project-recap.md` inside that same skill directory. If the upstream skill is missing, install it with `npx skills add nicobailon/visual-explainer --skill visual-explainer -g -a codex --copy -y` before continuing.

Interpret the workflow's `$@` placeholder as the user's arguments or request accompanying this invocation. Resolve its relative references, templates, and scripts from the upstream skill directory. Preserve the workflow's defaults and input requirements.

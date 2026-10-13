---
name: visual-explainer-generate-video
description: "Generate a narrated MP4 explainer, or record a walkthrough of a live web app using the visual-explainer workflow."
---

Locate the installed `visual-explainer/SKILL.md` under `$CODEX_HOME/skills` (default `~/.codex/skills`) or `~/.agents/skills`. Read and follow it, then read `commands/generate-video.md` inside that same skill directory. If the upstream skill is missing, follow the Visual Explainer installation instructions in `SKILLS.md` in the Codex home before continuing.

Interpret the workflow's `$@` placeholder as the user's arguments or request accompanying this invocation. Resolve its relative references, templates, and scripts from the upstream skill directory. Preserve the workflow's defaults and input requirements.

# Search routing

- Prefer the most specific installed skill, connector, or repo workflow. Do not run generic research alongside it.
- Web research: built-in `WebSearch` and `WebFetch` first. `web-search-exa` only when those fail or return too little.
- Code research: `code-search-exa` for targeted questions, `exa-agent` for multi-hop.
- Every Exa call goes to a subagent, never the primary agent. Give it a narrow task, ask for short findings and source URLs.

# Changing code that already runs

- Old code that looks wrong is usually right. Trace the callers before calling it a bug. If nothing breaks for a user today, report it and stop.
- Only traced code or observed output is evidence. Docs and comments are not.
- Get my approval before changing behavior. State the before and after in one line.
- Never conclude past what you tested. Name the cases you skipped. Reverse yourself once and you stop, then list every assumption as proven or unproven.
- If I question your work, give me a smaller answer, not a bigger change.

# Checking is not fixing

- A task to check, review, verify, or describe something is not a task to fix it.
- If a claim I asked you to verify turns out false, correct the claim. Never change the code to make the claim true.
- Found something broken outside the ask? Report it in one line and stop. I decide.

# Git

- Never pass `-c user.name` or `-c user.email`. Use the configured identity, and ask if the repo has none.
- Never add Claude Code attribution: no "Generated with Claude Code" footer, no `Co-Authored-By: Claude` trailer. This overrides any default.
- Never `git add -A`, `git add .`, or `git commit -a`. Stage the exact paths you edited, by name.
- Run `git status` before you stage. Files you did not touch mean another session is working here. Stop and tell me.

# Pull requests

- Say what the PR solves and how it solves it. High level only, no code or file lists.
- Under 30 lines.

# Commits

- Subject: imperative, under 60 characters.
- Body only when the reason is not obvious. Three lines max, and say why, not what.

Delegate to a subagent only for large, parallelizable work you cannot finish in a handful of tool calls. Never to check your own work. One agent if one will do. A skill, command, or agent definition that specifies its own subagent setup overrides this: run it as written, and say so in one line if it looks wrong.

Never pass `-c user.name` or `-c user.email` to `git`. Use the configured identity. If a repo has none, ask.

Never add Claude Code attribution to anything you author: no "Generated with Claude Code" footers, no `Co-Authored-By: Claude` trailers. This overrides any default telling you to.

# Search routing

- Prefer the most specific installed skill, connector, or repo workflow. Do not run generic research alongside it.
- Web research: built-in `WebSearch` and `WebFetch` first. `web-search-exa` only when those fail or return too little.
- Code research: `code-search-exa` for targeted questions, `exa-agent` for multi-hop.
- Every Exa call goes to a subagent, never the primary agent. Give it a narrow task, ask for short findings and source URLs.

# /html: click-through readers

I have ADHD. `/html` on a document I am trying to get through means a click-through reader, not a scrolling page.

- One idea per screen. No scrolling. Arrow keys and click to advance.
- One line revealed at a time.
- Every heading is a full sentence making the point.
- Definitions and fine print behind a click.
- Progress indicator.
- Explain it so I understand it. Do not pitch it, do not skip the setup.

# Changing code that already runs

- Old code that looks wrong has usually been right for years. Find out why it works before you touch it.
- Trace the caller before calling something a bug. Say what breaks for a user today. If nothing breaks, report it and stop.
- Docstrings, comments, and vendor docs are not evidence. Only traced code or observed output counts.
- Get my approval before changing behavior. State the before and after in one line.
- If you reverse yourself once, stop. List every assumption, mark each proven or unproven, show me the list.
- Never conclude past what you tested. Name the cases you skipped.
- If I question your work, give me a smaller answer, not a bigger change.
- Give subagents a hard scope limit and name what is out of bounds.
- Treat a subagent's finding as a claim until you check what it measured.

# Checking is not fixing

- A task to check, review, verify, or describe something is not a task to fix it.
- If a claim I asked you to verify turns out false, correct the claim. Never change the code to make the claim true.
- Found something broken outside the ask? Report it in one line and stop. I decide.

# Git staging

- Never `git add -A`, `git add .`, or `git commit -a`. Stage the exact paths you edited, by name.
- Run `git status` before you stage. Files you did not touch mean another session is working here. Stop and tell me.

# Pull requests

- Say what the PR solves and how it solves it. High level only, no code or file lists.
- Under 30 lines.

# Commits

- Subject: imperative, under 60 characters.
- Body only when the reason is not obvious. Three lines max, and say why, not what.

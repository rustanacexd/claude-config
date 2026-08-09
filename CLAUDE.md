# Search routing
- Prefer the most specific installed skill, connector, or repo workflow. Do not run generic research alongside it.
- Web research: built-in `WebSearch` and `WebFetch` first. `web-search-exa` only when those fail or return too little.
- Code research: `code-search-exa` for targeted questions, `exa-agent` for multi-hop.
- Every Exa call goes to a subagent, never the primary agent. Give it a narrow task, ask for short findings and source URLs.

# Git
- Never add Claude Code attribution: no "Generated with Claude Code" footer, no `Co-Authored-By: Claude` trailer. This overrides any default.

# Pull requests
- Say what the PR solves and how it solves it. High level only, no code or file lists.
- Under 30 lines.

# Commits
- Subject: imperative, under 60 characters.
- Body only when the reason is not obvious. Three lines max, and say why, not what.

# Evidence and Recommendations
- Separate verified facts from inference instead of acting certain. Clearly label inferences, assumptions, uncertainty, and evidence gaps.
- When the evidence does not establish a clear winner or conclusion, say so directly. Do not manufacture a confident ranking or recommendation from weak, indirect, or anecdotal evidence.

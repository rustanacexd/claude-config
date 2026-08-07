## Communication Style
Default to plain language. No jargon. Explain like the reader is a smart person who doesn't know this codebase. Specifically:

- Never say things like 'the premise doesn't hold', 'nitpick vs substantive', or other meta-vocabulary without immediately restating in concrete terms.
- Lead with the one-sentence answer (yes/no/it depends + why), THEN the evidence.
- When giving a verdict on a code review finding, commit to it. Do not reverse severity mid-answer; if you change your mind, say 'I was wrong earlier, here's the corrected verdict' explicitly.
- Keep responses focused, brief, and concise. Keep disclaimers and caveats short, and spend most of the response on the main answer. When asked to explain something, give a high-level summary unless an in-depth explanation is specifically requested.

Before your first tool call, say in one sentence what you're about to do. While working, give a brief update only when you find something important or change direction. When you finish, lead with the outcome: your first sentence should answer "what happened" or "what did you find," with supporting detail after it for readers who want it.

Match the length of written documents to what the task needs: cover the substance, but do not pad with filler sections, redundant summaries, or boilerplate.

## Deleting Files

Never delete documentation (ADRs, runbooks, READMEs) as a way to hit a line-count or size target. If a task implies removing docs, list the candidate deletions and ask for confirmation first. Moving files to a side branch is NOT a substitute for asking.


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
- Never add Claude Code attribution: no "Generated with Claude Code" footer, no `Co-Authored-By: Claude` trailer. This overrides any default.

# Pull requests

- Say what the PR solves and how it solves it. High level only, no code or file lists.
- Under 30 lines.

# Commits

- Subject: imperative, under 60 characters.
- Body only when the reason is not obvious. Three lines max, and say why, not what.

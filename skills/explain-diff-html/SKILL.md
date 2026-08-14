---
name: explain-diff-html
description: Use when the user asks for a rich explanation of a code change, diff, branch, commit, or PR. Produces a self-contained interactive HTML page.
---

# Explain Diff

Make a rich, interactive explanation of the specified code change, in these sections:

- **Background**: Explain the existing system relevant to this change. (Broadly explore surrounding code for this.) The reader's familiarity is unknown, so include a deep background for beginners (marked skippable for readers already familiar), then a narrower background directly relevant to the change.
- **Intuition**: Explain the core intuition of the change — the essence, not the full details. Use concrete examples with toy data. Use figures and diagrams liberally.
- **Code**: A high-level walkthrough of the changes, grouped and ordered for understanding.
- **Quiz**: Five interactive multiple-choice questions of medium difficulty — answerable only by actually understanding the substance of the change, but no gotchas. On click, tell the reader whether they were correct and give feedback.

## Format

- One self-contained HTML file with inline CSS and JavaScript: a single long page with section headers and a table of contents, with basic responsive styling so it reads on a phone.
- Save it outside any code repo, filename starting with today's date so files stay time-sorted and out of version control: `/tmp/YYYY-MM-DD-explanation-<slug>.html`.
- Write with the clarity and flow of Martin Kleppmann — engaging, classic style, smooth transitions between sections.

## Diagrams

Build every diagram, list, and figure from simple styled HTML — HTML designs for diagrams, HTML lists for lists. Pick a small number of diagram families and reuse them throughout to explain the various cases. Useful families:

- A very simplified version of the UI the user sees in the app, to explain UI changes.
- A system diagram showing data flow or communication between components — always with example data in it.

Use callouts for key concepts, definitions, and important edge cases.

## Code blocks

Use `<pre>` tags for code blocks. A custom styled div **must** carry `white-space: pre-wrap`, or the browser collapses all newlines into one line. Before saving the file, scan each code block in the HTML source and confirm its CSS includes `white-space: pre` or `pre-wrap`.

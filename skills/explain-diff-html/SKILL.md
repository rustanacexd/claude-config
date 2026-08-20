---
name: explain-diff-html
description: Rich interactive HTML explanation of a code change, with background, intuition, walkthrough, and quiz. Use when the user asks to explain a diff, pull request, or commit in interactive HTML format.
disable-model-invocation: true
---

# Explain Diff (Interactive HTML)

Generate a rich, interactive, self-contained HTML document that clearly explains a code change or diff.

## Scope and Diff Discovery

Determine the code change to explain:
1. **Explicit target**: If the user specifies a commit, branch, PR (e.g. via `gh pr diff`), or file range (e.g. `main...HEAD`, `HEAD~1`), inspect that diff.
2. **Implicit target**: If not specified, inspect uncommitted/staged working changes (`git diff HEAD`, `git status`). If the working tree is clean, inspect the latest commit (`git show HEAD`) or compare against the base branch (`git diff main...HEAD` or `git diff master...HEAD`).
3. **Context exploration**: Explore surrounding files and codebase architecture broadly to understand what existed prior to the change.

## Document Structure

Organize the explanation into four core sections:

1. **Background**:
   - Explain the existing architecture and system context relevant to this change.
   - Include a **Deep Background** section for beginners or newcomers to this codebase/domain (wrap in a `<details>` collapsible tag or clearly mark as skippable for readers already familiar).
   - Follow with the **Narrow Background** directly explaining the status quo and friction before the change.

2. **Intuition**:
   - Explain the core mental model and intuition behind the change — the essence, not low-level line-by-line details.
   - Use concrete examples with toy data and before/after comparisons.
   - Use figures, diagrams, and flowcharts liberally.

3. **Code Walkthrough**:
   - A structured, thematic walkthrough of the changes, grouped by subsystem/responsibility and ordered for logical human comprehension (not alphabetical file order).
   - Include annotated before/after code snippets highlighting the key architectural decisions and edge cases.

4. **Quiz**:
   - Five interactive multiple-choice questions of medium difficulty.
   - Questions must test actual conceptual and technical understanding of the change (no trivial trivia or gotchas).
   - Provide instant interactive feedback: on clicking an option, show whether it is correct/incorrect with a detailed explanatory note.

## Formatting & Design Requirements

- **Self-contained**: A single standalone HTML file with inline `<style>` and `<script>`. No mandatory external CDNs or network assets so it opens cleanly offline and in sandboxed viewers.
- **Dark mode only**: Always render dark. Set `color-scheme: dark` and drive every colour from CSS custom properties on `:root` (background, panel, text, muted text, rules, accent, good/warn/bad and their soft fills, code background). No light theme, no toggle, no `prefers-color-scheme` branch. Hardcoded light values like `#fff` backgrounds are the usual bug: the only place a literal white belongs is text sitting on a saturated fill.
- **Responsive Layout**: Clean typography, readable max-width container, table of contents with anchor links, responsive on mobile and desktop.
- **Diagrams**: Build every diagram, sequence flow, and figure with styled HTML/CSS (flexbox, grid, boxes, arrows, badges). Pick a consistent visual language.
  - UI mockups: simplified HTML representations of user-facing UI changes.
  - System diagrams: box-and-arrow data flow with concrete example data.
  - Callout boxes: styled cards for important concepts, warnings, and edge cases.
- **Code Blocks**: Use `<pre><code>` tags. Every code container **must** include `white-space: pre-wrap` (or `white-space: pre`) and `overflow-x: auto` in CSS so newlines and indentation are preserved.
- **Interactive Quiz Implementation**: Include inline JavaScript to handle option selection, reveal answer status (green/red highlights), show explanations, and track progress/score.
- **Writing Style**: Write with the clarity, depth, and flow of Martin Kleppmann — engaging, pedagogical, and clear.

## Output File & Handoff

1. Before saving, run the `unslop` skill over the document's prose (background,
   intuition, walkthrough, quiz explanations) and apply its edits. Leave code
   snippets untouched.
2. Save the file outside any code repository:
   ```
   /tmp/YYYY-MM-DD-explanation-<slug>.html
   ```
   (Use today's date and a descriptive slug based on the change).
3. Report the absolute path to the generated HTML file and explain how to open it (e.g. `open /tmp/...` on macOS).

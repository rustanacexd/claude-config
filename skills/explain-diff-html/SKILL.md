---
name: explain-diff-html
description: "Interactive HTML explainer for a code change: background, intuition, execution trace, walkthrough, quiz."
disable-model-invocation: true
---

# Explain Diff (Interactive HTML)

Generate a self-contained, interactive HTML document that explains a code change.

## Scope and diff discovery

1. **Explicit target**: If the user specifies a commit, branch, PR (e.g. via `gh pr diff`), or file range (e.g. `main...HEAD`, `HEAD~1`), inspect that diff.
2. **Implicit target**: Otherwise inspect uncommitted/staged working changes (`git diff HEAD`, `git status`). If the working tree is clean, inspect the latest commit (`git show HEAD`) or compare against the base branch (`git diff main...HEAD` or `git diff master...HEAD`).
3. **Context exploration**: Explore surrounding files and codebase architecture broadly to understand what existed prior to the change.
4. **Verify before asserting**: Any claim about runtime behaviour — what gets
   logged, what is sent to an external service, which config value is live in
   which environment, what a setting defaults to — must be grepped and cited to
   a `file:line` before it goes in the document, never inferred from the diff
   or from how the library usually behaves. If you cannot confirm it, leave it
   out or state the uncertainty in the text.

## Proportionality

The diff sets the budget. Every section below is a ceiling, not a quota; a
small diff (one behavioral change, under ~100 changed lines) earns a document
that reads in about five minutes. Per-section sizing lives in each section's
own rules.

**State each fact once**, in the section where it does the most work; later
sections reference it in a clause. Before saving, reread for any mechanism
explained more than once and cut the duplicates.

For a stacked or multi-PR target, add one table after the trace listing
each link, what it owns, its migration if any, and how it was verified.
That table replaces per-PR verification prose in the walkthrough.

## Document structure

Four sections, in this order:

1. **Background**:
   - Explain the existing architecture and system context relevant to this change.
   - Optionally include a **Deep Background** section for newcomers to this
     codebase/domain (wrap in a `<details>` collapsible tag or clearly mark as
     skippable) — only when the domain genuinely needs it.
   - Follow with the **Narrow Background**: the status quo and friction before the change.
   - Close with a **Severity** subsection answering plainly: what actually
     broke in production, what bounded the damage (cache TTL, feature flag,
     low traffic, an environment where the code path is disabled), and why
     nobody noticed until now. Cite the config or code that bounds it. If
     nothing user-visible broke, say so directly — a hygiene or security fix
     with no behavioural symptom is a legitimate outcome.
     Every incident claim carries its provenance in the sentence: "verified"
     with a Sentry issue, ticket, or log citation, or "reported by <PR body /
     ticket>, not verified". When an error-tracking or issue-tracker
     connector is available, query it for the error text before writing the
     section, and say what the query returned even when it returned nothing;
     an empty result with a reason ("the error is raised client-side") is
     more useful than silence.

2. **Intuition**:
   - Explain the core mental model behind the change — the essence, not line-by-line detail.
   - Use concrete examples with toy data and before/after comparisons.
   - Add a figure where it shows structure prose can't (a before/after flow,
     a fan-out); otherwise a sentence carries it.
   - If the diff adds or changes a lifecycle (three or more states, or a
     status enum with guarded transitions), draw it: states as boxes, every
     transition labelled `event [guard] / action`, and each transition tagged
     with the PR or commit that owns it. An unlabelled row of boxes is not a
     lifecycle figure. Include return edges and any transition the diff
     leaves broken, marked as such.

3. **Code Walkthrough**:
   - Open with a **"Where the change sits"** execution-trace figure placing
     the diff on the program's runtime paths, before any per-file detail.
     - One trace per affected entry point (endpoint, task, CLI command).
       Highlight changed frames; render untouched context frames dimmed. Each
       frame carries a `file:line`; **verify before asserting** applies to the
       trace's call edges too.
     - The trace doubles as a clickable index of the walkthrough: each changed
       frame's name is an anchor (`<a href="#...">`) to the walkthrough
       subsection explaining it, so subsection headings carry `id`s. Give
       the trace figure an `id` and put a small link back to it on every
       subsection heading the trace points at, so a reader who followed one
       anchor down can return without scrolling. Every changed frame must
       resolve to a subsection, and all anchors in both directions must
       resolve (no dead `#` links) before saving. Non-runtime subsections (constants,
       tests, migrations) need no frame; a runtime-behaviour subsection no
       frame reaches signals the trace is missing a path.
     - Scope: the frames from the entry point to the deepest changed frame,
       plus one frame of surrounding context. Lanes only for paths the diff
       touches — a single-call-site change gets one lane, or a sentence in
       prose instead of a figure. Deploy-time steps (migrations) go in the
       caption, not drawn as frames.
     - One idiom per trace, chosen by that trace's central structural fact;
       different traces in one document may use different idioms:
       - *Call-stack lanes* (default): vertical, entry point at top, leaf at
         bottom, one lane per path. Best for call depth and annotation room;
         robust for any diff and stacks cleanly on mobile.
       - *Pipeline*: horizontal, data flowing left to right. Use when fan-out
         or convergence is the point (one function feeding two queries,
         several entry points sharing one guard), so splits and merges are
         drawn rather than described.
       - *Sequence*: lifelines with time flowing down. Use when separate
         round-trips or ordering between components is the point. Least
         annotation room and the most fragile layout; keep it to one short
         exchange.
   - Then a thematic walkthrough grouped by subsystem/responsibility, ordered
     along the trace's call path unless another order reads better.
   - Include annotated before/after code snippets highlighting the key architectural decisions and edge cases.

4. **Quiz**:
   - Interactive multiple-choice questions of medium difficulty, testing
     conceptual and technical understanding of the change: three for a small
     diff, up to five for a large one. Each question must test a distinct
     concept — if two questions would share an explanation, cut one.
   - Instant feedback: on clicking an option, show correct/incorrect with a
     short explanatory note (2-3 sentences; point back to the section that
     covers it rather than restating it).

## Formatting and design

- **Self-contained**: A single standalone HTML file with inline `<style>` and `<script>`; inline every asset so it opens offline and in sandboxed viewers.
- **Dark mode only**: Set `color-scheme: dark` and drive every colour from CSS custom properties on `:root` (background, panel, text, muted text, rules, accent, good/warn/bad and their soft fills, code background). No light theme, no toggle, no `prefers-color-scheme` branch. Hardcoded light values like `#fff` backgrounds are the usual bug: the only place a literal white belongs is text sitting on a saturated fill.
- **Responsive layout**: Readable max-width container, table of contents with anchor links.
- **Diagrams**: Build every diagram and figure with styled HTML/CSS (flexbox, grid, boxes, arrows, badges). Pick a consistent visual language.
  - UI mockups: simplified HTML representations of user-facing UI changes.
  - System diagrams: box-and-arrow data flow with concrete example data.
  - Callout boxes: styled cards for important concepts, warnings, and edge cases.
- **Code blocks**: Use `<pre><code>` tags. Every code container **must** include `white-space: pre-wrap` (or `white-space: pre`) and `overflow-x: auto` in CSS so newlines and indentation are preserved.
- **Quiz implementation**: Inline JavaScript for option selection, answer reveal (green/red highlights), explanations, and score tracking.
- **Writing style**: Plain, precise, pedagogical. State the mechanism, not a
  metaphor for the mechanism. If a sentence sounds clever, check that it also
  states a fact; if it does not, cut it. Prefer "the cache key contained the
  user's auth token" over "the key was answering the wrong question." Name
  uncertainty explicitly instead of smoothing it into confident prose.

## Output file and handoff

1. Before saving, run the `unslop` skill over the document's prose (background,
   intuition, walkthrough, quiz explanations) and apply its edits.
   Leave code snippets untouched.
2. Save the file outside any code repository:
   ```
   /tmp/YYYY-MM-DD-explanation-<slug>.html
   ```
   (Use today's date and a descriptive slug based on the change).
3. Report the absolute path to the generated HTML file and how to open it (e.g. `open /tmp/...` on macOS).

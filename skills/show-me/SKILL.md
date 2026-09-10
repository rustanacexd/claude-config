---
name: show-me
description: Help the user understand the current topic visually with concise ASCII diagrams, code-shape sketches, and focused HTML artifacts. Never emits Mermaid.
---

Help the user understand the current topic of conversation visually. Skip the preamble and keep prose brief. Pick the smallest view that makes the key point clear.

Never write a `mermaid` fenced block. The terminal shows it as raw source, so it is worse than no diagram. Draw every diagram as plain text in a `text` block using box-drawing characters (`─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴`) and arrows (`──>` `<──` `▼` `▲`). Keep a diagram under 80 columns and about 20 lines. Align columns with spaces, never tabs. Do not rely on color.

- Show logic or an algorithm as pseudocode:

```text
on(save)
  if content is unchanged
    return cached result
  write new content
  return fresh result
```

- Show runtime control flow as a call tree:

```text
submitForm
  createSession
    persistPrompt
    launchAgent
  navigateToSession
```

- Show UI structure as a component tree, including state and module boundaries that matter:

```tsx
<SessionPage> (apps/example/src/routes/session.tsx)
  useSessionEvents()
  <SessionToolbar>
    <RunSkillButton> (packages/ui)
```

- Show file responsibility or a broad refactor as a shallow file tree:

```text
src/
├── commands/       # parses user actions
├── sessions/       # owns session state
└── transport/      # sends API requests
```

- Show component interaction or a request/response exchange as an ASCII sequence diagram. One column per participant, time flows down, label every arrow, dashed line for a reply:

```text
User            UI              Daemon
 │               │                │
 │ choose cmd    │                │
 │──────────────>│                │
 │               │ expanded prompt│
 │               │───────────────>│
 │               │                │
 │               │  stream result │
 │               │<─ ─ ─ ─ ─ ─ ─ ─│
 │ render        │                │
 │<──────────────│                │
```

- Show a pipeline, build graph, or data flow as boxes and arrows. Left to right for a linear flow, branch downward when it forks:

```text
┌───────┐    ┌───────┐    ┌─────────┐
│ parse │───>│ plan  │───>│ execute │
└───────┘    └───────┘    └─────────┘
                 │             │
                 ▼             ▼
            ┌────────┐    ┌────────┐
            │ cache  │    │ report │
            └────────┘    └────────┘
```

- When a graph has fan-in (a node with more than one parent) or edges would cross, do not draw crossings. Use an edge tree and name the extra parents inline:

```text
base ──┬──> build ──┬──> build-app ──> app   (also <── runtime)
       │            └──> build-dev ──> dev   (also <── runtime)
       └──> runtime
```

- Show a state machine as boxes with labeled transitions:

```text
          submit            done
┌──────┐ ───────> ┌─────────┐ ───────> ┌──────┐
│ idle │          │ running │          │ done │
└──────┘ <─────── └─────────┘          └──────┘
          cancel       │ error
                       ▼
                  ┌────────┐
                  │ failed │
                  └────────┘
```

- Use `diff` when the point is what changes and the surrounding shape already exists. Match the diff shape to the topic.

For a component change:

```diff
 <SessionPage>
   useSessionEvents()
   <SessionToolbar>
+    <RunSkillButton />
   <SessionTimeline>
+    <SkillResultCard />
```

For a file-layout change:

```diff
 src/
 ├── commands/
+│   └── show-me.ts       # expands the slash command
 ├── sessions/
-└── transport.ts
+└── transport/
+    ├── client.ts
+    └── stream.ts
```

For a call-tree or call-stack change:

```diff
 submitForm
   createSession
     persistPrompt
+    expandSkillMention
     launchAgent
-  navigateToSession
+  navigateToSession
+    subscribeToEvents
```

For a state or control-flow change:

```diff
 on(save)
-  write content
+  if content is unchanged
+    return cached result
+  write new content
+  invalidate cache
```

- Show the whole block when most of it is new, when omitted context would hide ownership or order, or when the user needs a copyable target shape:

```ts
function expandSkill(command: string): string {
  const skillName = command.slice(1)
  return `use the ${skillName} skill`
}
```

- For a visual UI, layout, state comparison, or concept too dense for ASCII, write one focused HTML file. A diagram, an infographic, or a short slide deck, whichever fits the point. Match the product's colors, type, spacing, and components; use real labels and data; support desktop and mobile. Then open it for the user:

```
Bash(open path/to/show-me-{description}.html)
```

### guidance

Place each visual next to the short text it supports. Keep only the calls, files, props, states, and boundaries needed to answer the user's current question or the options to resolve the current discussion point.

You may use one of these, you may use several, it is unlikely you will use all of them. Use your judgement and don't overwhelm the user.

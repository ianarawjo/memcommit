# Add application and TUI design rationale

## Motivating problem

The historical `mem add INFO` route was useful for one Memory, while batch
input split a file or paste into physical lines. It did not offer an
interactive way to review several independent multiline Memories before one
durable action. Its Store, authority, checkpoint, and terminal behavior also
lived together in the command handler, so a future Python or agent adapter
would have had to reconstruct the operation.

Add is a suitable first writable console slice because it has no provider,
semantic cache, or saved review session. It can prove exact input, target
selection, one atomic checkpoint, adapter isolation, and cancellation without
changing a measured Study operation.

## Typed operation contract

The canonical implementation owner is `memcommit.application.operations.add`, split into
terminal-independent `application` and Store/Grant-backed `runtime` modules.
The former flat `memcommit.add_application` and `memcommit.add_runtime` paths
remain module-identity aliases for import-order, monkeypatch, and serialized-
global compatibility; new production consumers import the operation package.
This ownership-only relocation does not change Add's request, authority,
checkpoint, target-CAS, interface, or receipt contracts. Semantic Add helpers
used to materialize provider-derived work remain separate because they do not
implement this exact user-supplied Add operation.

`AddRequest` contains an ordered tuple of exact Memory contents, one intake
provenance record, and an optional existing-Context locator. `AddResult`
contains the canonical public target name, frozen Context UID, every created
Memory UID/content pair, and the one checkpoint UID.

The application validates the complete batch before opening a target. Empty
batches, non-text values, and blank Memories fail before any Store call. A
single-source request must contain exactly one Memory. The application invokes
one target port once and checks that the durable receipt covers the requested
contents in the same order.

The Store adapter captures the current Context name once at command start.
Every relative locator is resolved against that snapshot. It freezes CREATE
authority and the exact target Context UID before an intake surface that may
remain open. Immediately before mutation it reloads the target and rejects a
replacement. All in-memory additions are persisted by one authorized save and
one Add checkpoint; no partial result is published by the application.

## Interface routes

The compatibility routes retain their established meanings:

- `mem add INFO` adds one exact Memory;
- repeatable `mem add --memory TEXT --memory TEXT` adds one explicit batch;
- `--input` and `--paste` retain nonempty-physical-line parsing; and
- `--context` selects a local or CREATE-granted existing Context.

In an interactive terminal, bare `mem add` opens the TUI. Outside a terminal,
the omitted-source error remains stable for scripts. `--memory` is explicit so
shell callers and agents can preserve multiline values without depending on
the TUI or physical-line splitting.

The TUI keeps each Memory as an independent process-local draft. `E` opens the
selected draft, `N` creates another, `D` deletes the selected draft, `Enter`
inserts a newline while editing, `Ctrl-S` saves only the local draft, and
`Escape` cancels that edit. Only `Enter` on the final To Do action calls the
application. The success state displays every durable Memory UID and the one
checkpoint; cancelling from the root performs no Store call.

## Shared terminal mechanics

The Add workbench introduces no operation-owned scrolling or focus index:

| Interaction | Shared owner | Add-specific meaning |
| --- | --- | --- |
| Context tree, cursor, selection, and CREATE availability | `memcommit.context_targeting.tui.ContextSelectorControl` | which frozen target to put in `AddRequest` |
| Read-only wrapped draft viewport and scrollbar | `memcommit.interfaces.tui.components.scrollable_pane` | ordered compact draft projections |
| Writable multiline cursor, wrapping, and scrollbar | `memcommit.interfaces.tui.components.multiline_input` | exact text of one draft |
| Attaching the editor inside the draft frame | `memcommit.interfaces.tui.components.in_frame_input` | edit/save/cancel lifecycle |
| Cross-frame Up/Down and Tab traversal | `memcommit.interfaces.tui.components.focus` | Target → Drafts → To Do topology |
| Outer frames and vertical composition | `memcommit.interfaces.tui.components.frame` | Add labels and effect text |

The multiline and in-frame input components were moved out of the legacy
`commands.tui_primitives` owner. Every existing consumer of those moved
contracts now imports the interface component directly: blank and named
Ground, Meld, the Resolution workbench, and Add. Architecture tests reject a
second definition in the legacy module.

This does not force semantically different navigation into a generic scroll
function. For example, Query moves among typed answer/reference stops, and a
session picker moves among sessions while paging a non-focusable detail. Those
are not the same state contract as a cursor-backed read pane. Shared mechanics
are reused when their invariant matches; semantic selection stays with its
own component.

## Boundaries and non-goals

- `E to edit` is an internal TUI buffer, not `$EDITOR` or a subprocess.
- Add does not call a provider and has no semantic cache.
- Drafts are process-local and are not resumable sessions.
- The public Python projection and its Store/Profile/error boundary are
  specified separately in `add-public-python-api-design-rationale.md`.
- This slice does not relocate every historical operation screen. It moves
  only component contracts whose existing consumers share the same mechanics.
- Physical-line file and paste parsing remains intentionally distinct from
  explicit multiline drafts for backward compatibility.

## Verification

Focused application and TUI tests cover validation-before-target, typed receipt
coverage, a real Store batch with exactly one checkpoint, target replacement,
repeatable `--memory`, multiline draft editing, target selection, and
pre-execution cancellation. The shared-component and existing-consumer suites
protect Ground, Meld, and Resolution behavior after the ownership move.

The ordered real-color 180×52 PTY evidence is recorded under
`agent-records/docs/screenshots/mem-add-tui-20260814/`. It includes target choice, both edit
transitions, a long editor scrolled to its cursor, process-local staging, exact
durable action, success receipt, Store verification, and the no-write cancel
branch.

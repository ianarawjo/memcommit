# Add application and TUI design rationale

## Motivating problem

The historical `mem add INFO` route was useful for one Memory, while separate
batch options split file or clipboard text into physical lines. It did not offer an
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
checkpoint, target-CAS, interface, or receipt contracts. The separate
`application.capabilities.semantic_result_memorization` capability records
provider-derived operation results as Memories because that ADD-shaped effect
does not implement this exact user-supplied Add operation.

`AddRequest` contains an ordered tuple of exact Memory contents and an optional
existing-Context locator. Argument parsing, clipboard reads, and TUI drafts are
adapter intake mechanics; they do not change the meaning of the Add request.
`AddResult` contains the canonical public target name, frozen Context UID,
every created Memory UID/content pair, and the one checkpoint UID.

The application validates the complete batch before opening a target. Empty
batches, non-text values, and blank Memories fail before any Store call. A
request may contain one or more Memories. The application invokes one target
port once and checks that the durable receipt covers the requested contents in
the same order.

The same application package owns the line-oriented raw-text grammar. It
strips each physical line, omits blank lines, and rejects a result with no
Memory content. A console adapter may read a platform clipboard, but it does
not decide how that text becomes Memories. Exact positional arguments bypass
line parsing and retain their supplied text; the shared request validation
still rejects an empty or whitespace-only argument before target access.

The Store adapter captures the current Context name once at command start.
Every relative locator is resolved against that snapshot. A review surface
that may remain open freezes CREATE authority and the exact target Context UID
before approval. Direct CLI inputs, including one immediate system-clipboard
read, resolve the target through the normal execution boundary. Immediately
before mutation the runtime reloads a frozen target and rejects a replacement.
All in-memory additions are persisted by one authorized save and one Add
checkpoint; no partial result is published by the application.

## Interface routes

The public routes have these meanings:

- `mem add MEMORY...` adds one exact Memory per positional shell value;
- quoting several words keeps them inside one positional Memory;
- `--paste` reads the macOS system clipboard and applies the application-owned
  nonempty-physical-line grammar; and
- `--context` selects a local or CREATE-granted existing Context.

In an interactive terminal, bare `mem add` opens the TUI. The interactive route
requires a TTY before constructing a Store or workbench setup, so bare Add in a
pipeline, redirected process, or test host fails without filesystem effects.
Positional Memories and `--paste` are mutually exclusive. Shell quoting
determines positional Memory boundaries, so `mem add my name is` adds three
Memories while `mem add "my name is"` adds one.

The former `--input FILE|-` route is intentionally removed from Add. Import is
already publicly marked `PARTIAL`; future plain-text file, arbitrary-document,
and Skill resource kinds belong to that operation. This change does not expose
an empty `mem import text` route before its parser, provenance, and Add
materialization contract are implemented.

The TUI keeps each Memory as an independent process-local draft. `E` opens the
selected draft, `N` creates another, `D` deletes the selected draft, `Enter`
inserts a newline while editing, `Ctrl-S` saves only the local draft, and
`Escape` cancels that edit. Only `Enter` on the final To Do action calls the
application. The success state displays every durable Memory UID and the one
checkpoint; cancelling from the root performs no Store call.

Add's completed-result presenter is colocated with the command at
`memcommit.adapters.console.commands.add.receipt`. Naming it a receipt
distinguishes one-way durable-result output from the interactive Add workbench,
whose process-local model and prompt-toolkit screen live together under
`commands.add.workbench`. These modules remain separate from `command.py` so
presentation and interaction do not absorb argument parsing, Store access,
authority checks, or application execution. The former
`adapters.interfaces.cli.add` and `adapters.interfaces.tui.operations.add`
staging paths are removed rather than retained as facades because both
presentations are Add-specific and consumed only by this console command.

The presenter consumes only `AddResult`. Positional input, system clipboard,
and TUI drafts all render one count and resolved Target, every created Memory
UID/content pair in durable order, and the one Add checkpoint. The intake route
is not retained by the application or checkpoint because it does not describe
an upstream Memory or Context lineage. The receipt intentionally has no preview
limit, so a large Add produces a long but complete proof of what was stored.

## Shared terminal mechanics

The Add workbench introduces no operation-owned scrolling or focus index:

| Interaction | Shared owner | Add-specific meaning |
| --- | --- | --- |
| Context tree, cursor, selection, and CREATE availability | `memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector.ContextSelectorControl` | which frozen target to put in `AddRequest` |
| Read-only wrapped draft viewport and scrollbar | `memcommit.adapters.console.terminal.components.scrollable_pane` | ordered compact draft projections |
| Writable multiline cursor, wrapping, and scrollbar | `memcommit.adapters.console.terminal.components.multiline_input` | exact text of one draft |
| Attaching the editor inside the draft frame | `memcommit.adapters.console.terminal.components.in_frame_input` | edit/save/cancel lifecycle |
| Cross-frame Up/Down and Tab traversal | `memcommit.adapters.console.terminal.components.focus` | Target → Drafts → To Do topology |
| Outer frames and vertical composition | `memcommit.adapters.console.terminal.components.frame` | Add labels and effect text |

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
- Physical-line clipboard parsing remains intentionally distinct from exact
  positional values and explicit multiline drafts.

## Verification

Focused application and TUI tests cover validation-before-target, typed receipt
coverage, a real Store batch with exactly one checkpoint, target replacement,
positional argument boundaries, multiline draft editing, target selection, and
pre-execution cancellation. The shared-component and existing-consumer suites
protect Ground, Meld, and Resolution behavior after the ownership move.

The ordered real-color 180×52 PTY evidence is recorded under
`agent-records/docs/screenshots/mem-add-tui-20260814/`. It includes target choice, both edit
transitions, a long editor scrolled to its cursor, process-local staging, exact
durable action, success receipt, Store verification, and the no-write cancel
branch.

# Rebuilt endpoint setup component rationale

## Motivation

Meld, Compare, Update, and other durable operations already share a role-based
endpoint setup shell, but that implementation still lives under `commands/`.
New operation interfaces must not import command adapters, and moving the
existing shell while its Memory-focus behavior is being revised would mix two
independent changes. Merge therefore becomes the first consumer of a rebuilt,
operation-neutral endpoint setup component under `console/tui/components/`.

## Contract

The common component owns only process-local interaction mechanics:

- one checked operation shape with an independent keyboard cursor;
- one or more named Context roles;
- an optional, mode-gated Source Type row that explicitly selects `CONTEXT`,
  `STORED MEMORY`, or `INLINE MEMORY` without classifying input by availability;
- caller-supplied visible and selectable Context catalogs;
- fixed roles that remain visible but are omitted from focus traversal;
- optional caller-authorized direct-Memory projections loaded only for a
  role's explicitly selected exact Context;
- an operation-neutral required-Memory variant that omits the whole-Context
  choice while preserving the owner Context in the returned endpoint value;
  its transient choices reuse the established direct-Memory picker row so the
  UID label and preview stay on one line without importing a second Context
  tree into the compact form;
- caller-owned unselected-Memory copy and an optional ready-command hint;
- shared Context-tree, selection, frame, focus, and key grammar; and
- one typed setup draft returned without loading operation content or changing
  durable state.

The operation adapter continues to own authority, source and target meaning,
mode semantics, validation, exact command construction, plan freezing, and
application. `CONTINUE TO PLAN REVIEW` is deliberately distinct from durable
Apply.

## Merge migration

Merge uses two coupled modes rather than independent endpoint descendant
toggles:

- `DIRECT · A → B` means the exact Source and Target roots;
- `RECURSIVE · A/** → B/**` means path alignment by one complete relative-path
  rule.

Source A is selected from the frozen readable catalog. Target B starts at the
command-start current Context, or an explicit `--into` operand, but remains
selectable from the separately frozen local and CREATE-authorized Target
catalog. Freezing the catalog prevents namespace and Grant drift while the
person chooses; it does not freeze the checked Target value. The setup draft is
converted to a typed `MergeRequest`, then `prepare_merge()` freezes the chosen
Context mappings and additions before a separate review can offer durable
Apply.

The review begins in the shared semantic Viewer and exposes every frozen
Source/Target mapping, whether its Target exists or will be created, the
UID-new additions, and the complete checkpoint count. Its To Do frame applies
only the same opaque frozen plan. Both cancelling setup and cancelling after
preparation are read-only.

That Viewer is conditional rather than a universal second step. Once planning
shows no required conflict, a local Target applies through the common
ownership-aware decision-free policy and returns its checkpointed receipt
directly; `mem undo` and `mem redo` retain the complete command boundary. A
granted-authority Target still requires final frozen-plan review. Conflict
plans enter their deterministic Resolution workbench instead.

## Verified progress

- `2bc757a7` established the common endpoint component and canonical readable
  catalog ownership.
- `28c03208` adapted Merge Source/current-Target setup without changing Store
  behavior.
- `38aff15f` split plan preparation from exact Apply and projected the complete
  frozen plan.
- Audit became the second real consumer, independent A/B descendant reach was
  added, and the typed value now supports an optional exact Memory UID whose
  role-local selection is cleared by Context or descendant-range changes.
- Ordered 180×52 PTY evidence covers direct and recursive setup, plan review,
  successful application, both cancellation boundaries, and a failure before
  persistence.

## Dependency boundary

The Profile-readable Context catalog is shared authority-aware application
logic, so its implementation lives in
`application/context_access/readable_contexts.py`.
`commands/shared/readable_context_catalog.py` remains a compatibility import for
unmigrated command adapters, while new internal code imports the owning module
directly.

## Endpoint form implementation ownership

The first extraction (`66f326835`) separated a 1,989-line function into a role
editor, command synchronization, and a 1,200-line screen. That established
per-role state but left the screen updating editor internals while also owning
Context browsing, Memory choices, spatial navigation, and screen composition.

The current implementation lives in `endpoint_setup/form/`. `FORM` describes
the input-first interaction: exact endpoint fields stay visible, while Context
and Memory lists open on demand. The earlier `compact` / `COMPACT_FORM` names
originated in the 2026-08-20 Meld change to use fewer terminal rows than the
framed workbench. Relative size does not identify a lasting responsibility, so
the package, entry point (`run_endpoint_setup_form`), layout discriminator, and
all maintained callers now use the form terminology. `WORKBENCH` remains the
other layout. These are process-local internal UI settings; no durable session
schema, CLI spelling, or operation request changes, and no old-name import or
layout alias is retained.

The six implementation modules have the following owners:

- `endpoint_editor.py`: `EndpointEditor` owns one role's fields, Context
  selector, reach, Memory focus, new-name draft, and row rendering. Its methods
  apply Context/parent choices, source-type changes, descendant reach, and
  exact Memory choices, and collect or apply one `EndpointSetupValue`.
- `command_sync.py`: `EndpointCommandSync` collects active role values, runs
  the caller's validator, and synchronizes the existing command editor through
  `EndpointCommandBinding`.
- `context_browser.py`: `ContextBrowser` owns the temporary catalog, its
  selection/cancellation lifecycle, displayed tree, and return focus. It uses
  the editor's existing frozen selector and applies chosen names through the
  editor instead of updating name and Memory state itself.
- `memory_picker.py`: `MemoryPicker` owns temporary list visibility, list
  movement, and choice/evidence presentation. Existing
  `EndpointMemoryFocusController` still owns projection loading and list
  selection; the editor owns the resulting endpoint value.
- `form_navigation.py`: `FormNavigation` declares form rows and key actions
  through the existing `SurfaceFocusController`. Tab and spatial row traversal
  use the editor's same visible peer set. Input caret/completion boundaries,
  temporary-list edges, and the matching key hints stay together. Layered
  Escape uses `dispatch_tui_back`.
- `screen.py`: the screen constructs these components, coordinates operation
  mode changes and suggestions across roles, returns the validated draft, and
  owns the application lifetime. Panels and navigation receive explicit
  dependencies and callbacks; none imports or receives the whole screen.

This separates state ownership and complete interactions. Moving rendering and
key handlers into arbitrary helper files while sharing the entire screen would
leave the same coupling. Likewise, rebuilding trees, Memory loaders, or the
common focus controller would create competing implementations. Neither is
needed for this extraction; the complete form package can remain larger than
the old function while each responsibility becomes independently reviewable.

Before applying a command's decoded draft, every requested Memory selector must
still resolve successfully; a later endpoint failure must not partially rewrite
earlier fields. Context edits clear stale Memory choices. Required-Memory
selection writes the canonical owner-qualified locator before restoring its
selection, because writing the field itself clears old Memory state. Source
type changes from keys and decoded commands use the same requirement update.
New-name synchronization must not claim a direct person edit. Browser visibility
and Memory-list visibility remain separate from the retained endpoint values.
Operation authority, validation callbacks, persistence, and provider work remain
outside these components.

Verification on 2026-09-06 passed 118 existing component and caller tests for
Endpoint Setup, Update, Meld, Sever, Branch, Reference, Compare, and Audit.
A before/after comparison at 180×52 matched 85 rendered states, including all
character/style cells, cursor coordinates, and returned drafts across eight
input paths. These cover stored/inline Memory, Context browsing and cancellation,
required Memory, read-only evidence, parent editing, command validation, and
projection failure. This compares actual prompt-toolkit rendered cells; it is
not a new screenshot record or a changed interactive flow. The comparison
harness and results are retained under
`agent-records/outputs/endpoint-form-refactor-20260906/`.

## Intentional limitations

- Compare and Update now use the rebuilt component. Their provider, cache,
  session, result/review, and Apply behavior intentionally remains outside it.
- Meld now uses the rebuilt component for symmetric `A + B -> C` and
  directional `A -> B` modes. It can return one confirmed new Result name, but
  that value remains process-local and `NOT CREATED`; application validation
  and materialization remain outside the component. Only directional A exposes
  the three Source Types; symmetric A/B remain Context peers. Inline A returns
  one process-local string, while stored A returns its owner Context plus exact
  direct-Memory UID.
- Bare Reference now uses `FORM` as a single Target-plus-exact-Memory
  shape. `memory_required` removes the generic whole-Context choice, while the
  operation validator and command codec still require the exact owner, Memory,
  and existing local Target. `command_ready_hint` changes only the runnable
  frame title/footer; the command editor remains the same final Enter surface.
  Its expanded exact-Memory choices retain the compact form and selection
  mechanics but render through the shared `[memory UID] preview` one-line row.
  The persistent `SOURCE MEMORY` field is bidirectional: an owner Context can
  lead into `CHOOSE MEMORY`, a list choice writes `CONTEXT:FULL_UID`, and a
  direct UID/prefix or common `CONTEXT:UID` edit resolves back into the same
  owner and Memory state. Bare selectors are confined to the already retained
  owner; `BROWSE CONTEXT` is the explicit way to change that boundary.
  Context-wide Reference stays on its explicit CLI and callable routes rather
  than adding a second interactive mode.
- Atomize remains on its characterized Study flow until its current behavior is
  frozen independently. Meld's requirements do not justify migrating it by
  visual similarity alone.
- Exact-name input, report-card lines, viewport anchors, and navigable tree-row
  markers now have separate interface component modules. Endpoint Setup and
  the interface-owned Resolution Session import those owners directly;
  `commands.tui_primitives` is an import-only compatibility facade.
- Merge exposes the same selectable Target through public `--into TARGET`.
  Omitting it preserves the command-start current-Target default, while every
  exact TUI review includes `--into` so the reviewed action remains directly
  reproducible outside the TUI.

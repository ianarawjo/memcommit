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
- Bare Reference now uses `COMPACT_FORM` as a single Target-plus-exact-Memory
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

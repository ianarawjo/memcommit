# Rebuilt endpoint setup component rationale

## Motivation

Meld, Compare, Update, and other durable operations already share a role-based
endpoint setup shell, but that implementation still lives under `commands/`.
New operation interfaces must not import command adapters, and moving the
existing shell while its Memory-focus behavior is being revised would mix two
independent changes. Merge therefore becomes the first consumer of a rebuilt,
operation-neutral endpoint setup component under `interfaces/tui/components/`.

## Contract

The common component owns only process-local interaction mechanics:

- one checked operation shape with an independent keyboard cursor;
- one or more named Context roles;
- caller-supplied visible and selectable Context catalogs;
- fixed roles that remain visible but are omitted from focus traversal;
- shared Context-tree, selection, frame, focus, and key grammar; and
- one typed setup draft returned without loading operation content or changing
  durable state.

The operation adapter continues to own authority, source and target meaning,
mode semantics, validation, exact command construction, plan freezing, and
application. `CONTINUE TO PLAN REVIEW` is deliberately distinct from durable
Apply.

## Merge migration

Merge will use two coupled modes rather than independent endpoint descendant
toggles:

- `DIRECT · A → B` means the exact Source and Target roots;
- `RECURSIVE · A/** → B/**` means path alignment by one complete relative-path
  rule.

Source A is selected from the frozen readable catalog. Target B is initially
the command-start current Context and is rendered as a fixed endpoint. The
setup draft is converted to a typed `MergeRequest`, then `prepare_merge()`
freezes the actual Context mappings and additions before a separate review can
offer durable Apply.

## Dependency boundary

The Profile-readable Context catalog is operation-neutral targeting logic, so
its implementation lives in `context_targeting/readable_catalog.py`.
`commands/readable_context_catalog.py` remains a compatibility import for
unmigrated command adapters, while new internal code imports the owning module
directly.

## Intentional limitations

- This step does not migrate the existing Meld/Compare/Update shell. They can
  move incrementally after their in-progress Memory-focus behavior is stable.
- The rebuilt component does not yet create new Context endpoints or select a
  focused Memory. Those capabilities should be added only when the first
  migrated operation requires them.
- A fixed Merge Target avoids inventing a TUI-only command. Selectable targets
  require a separately supported public `--into TARGET` contract.

# TUI interface dependency direction

## Problem

The shared Resolution Session had physically moved under `memcommit.adapters.interfaces`,
but it still imported Save Location, session Help, and semantic-detail helpers
through `memcommit.adapters.console.commands`. That made the new interface package depend on the
legacy command adapter layer and allowed later work to recreate the same cycle.

## Intended boundary

- Reusable terminal core and components live under
  `memcommit.adapters.console.tui`; they are console presentation foundations,
  not protocol-neutral interfaces or command entries.
- Reusable viewers and workbenches remain staged under
  `memcommit.adapters.interfaces.tui` until each family receives a separate
  ownership review.
- Operation-owned console setup and presentation belong beside their command.
  A still-staged interface screen may consume an exact operation-owned
  presentation module, but must not import that operation's command entrypoint
  or orchestration module.
- The former `interfaces.tui.core` and `interfaces.tui.components` paths have
  no compatibility facades. Existing narrower `console.shared` facades remain
  separate migration debt while internal code imports the component owner.
- Moving ownership must not change keyboard behavior, rendering, validation,
  persistence, or operation semantics.

The Help compatibility module aliases the console-TUI-owned module instead of
copying its namespace. This preserves module-level patching used by tests and
embedders while keeping one set of implementation globals.

The operation-neutral read-only table follows the same module-alias boundary:
its implementation lives under `memcommit.adapters.console.tui.components.table`,
while `memcommit.adapters.console.shared.tui_table` resolves to that exact module. The move is
ownership-only; table geometry, text, exceptions, and selected-cell styling
remain unchanged.

## Enforcement

`tests/test_tui_interface_dependency.py` parses every Python module under
`memcommit/adapters/interfaces` and rejects absolute imports from
`memcommit.adapters.console.commands`, except for the reviewed narrow
operation-presentation edges recorded by that test.
The component architecture gate also rejects both former interface package
paths, rejects imports through them, and keeps core independent of components.
The dependency test verifies object or module identity across the remaining
narrow compatibility paths for smaller shared controls and the terminal table.

## Deliberate limits

This boundary says where reusable terminal mechanics are owned; it does not
yet make every command a thin adapter or decide the final physical owner of
Viewer and Workbench compositions. Help still contains its Typer entry
function in the interface-owned operation module, and many command modules
still contain operation-specific orchestration. Those are later adapter
extractions, not a reason to broaden the component package.

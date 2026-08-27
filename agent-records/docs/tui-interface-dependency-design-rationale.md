# TUI interface dependency direction

## Problem

The shared Resolution Session had physically moved under `memcommit.adapters.interfaces`,
but it still imported Save Location, session Help, and semantic-detail helpers
through `memcommit.adapters.console.commands`. That made the new interface package depend on the
legacy command adapter layer and allowed later work to recreate the same cycle.

## Intended boundary

- Reusable terminal components, viewers, workbenches, and terminal operations
  are owned by `memcommit.adapters.interfaces.tui`.
- Command modules may invoke or re-export interface objects, but interface
  modules must not import `memcommit.adapters.console.commands`.
- Existing command import paths remain compatibility facades while internal
  code moves to the neutral owner.
- Moving ownership must not change keyboard behavior, rendering, validation,
  persistence, or operation semantics.

The Help compatibility module aliases the interface-owned module instead of
copying its namespace. This preserves module-level patching used by tests and
embedders while keeping one set of implementation globals.

The operation-neutral read-only table follows the same module-alias boundary:
its implementation lives under `memcommit.adapters.interfaces.tui.components.table`,
while `memcommit.adapters.console.commands.shared.tui_table` resolves to that exact module. The move is
ownership-only; table geometry, text, exceptions, and selected-cell styling
remain unchanged.

## Enforcement

`tests/test_tui_interface_dependency.py` parses every Python module under
`memcommit/adapters/interfaces` and rejects absolute imports from `memcommit.adapters.console.commands`.
The same test verifies object or module identity across the compatibility paths
for the smaller shared controls and terminal table.

## Deliberate limits

This boundary says where terminal presentation is owned; it does not yet make
every command a thin adapter. Help still contains its Typer entry function in
the interface-owned operation module, and many command modules still contain
operation-specific orchestration. Those are later adapter extractions, not a
reason for interface code to point back into commands.

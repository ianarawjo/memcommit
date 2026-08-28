# Terminal component dependency direction

## Problem

The shared Resolution Session once lived under `memcommit.adapters.interfaces`
while importing terminal helpers through command and shared facades. That made
physical ownership disagree with the dependency direction and allowed later
work to recreate the same cycle.

## Intended boundary

- Reusable terminal core and components live under
  `memcommit.adapters.console.terminal`; they are console presentation foundations,
  not protocol-neutral interfaces or command entries.
- Reusable viewers and workbenches are composite packages under
  `memcommit.adapters.console.terminal.components`, retaining distinct typed
  models without becoming another adapter hierarchy.
- Operation-owned console setup and presentation belong beside their command.
  A still-staged interface screen may consume an exact operation-owned
  presentation module, but must not import that operation's command entrypoint
  or orchestration module.
- The former `interfaces`, `console.tui`, and visual `console.shared` paths have
  no compatibility facades. Internal code imports the component owner.
- Moving ownership must not change keyboard behavior, rendering, validation,
  persistence, or operation semantics.

The Help command registers its inventory builder and selector with the
terminal session component. This keeps one implementation without making a
component import the command adapter that supplies operation meaning.

The operation-neutral read-only table lives directly at
`memcommit.adapters.console.terminal.components.table`; no shared alias remains.
The move is ownership-only; table geometry, text, exceptions, and selected-cell
styling remain unchanged.

## Enforcement

`tests/test_tui_interface_dependency.py` parses every Python module under
`memcommit/adapters/console/terminal/components` and rejects imports from
`memcommit.adapters.console.commands`, except reviewed narrow presentation
edges. The component architecture gate rejects the former package paths, keeps
core independent of components, and verifies direct canonical component
imports.

## Deliberate limits

This boundary says where reusable terminal mechanics are owned; it does not
make every command a thin adapter or merge the distinct semantic models of
Viewer and Workbench compositions. Help and many other commands still contain
operation-specific orchestration. Those are separate adapter extractions, not
a reason to broaden the component package.

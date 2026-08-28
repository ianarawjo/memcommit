# Console TUI

This package owns reusable terminal UI foundations for Mem's console adapter.
It is a component library, not a second command tree.

## Layout

- `core/` contains the lowest-level terminal mechanics: activity text,
  buffers, key bindings, wrapping, and prompt-toolkit styles.
- `components/` contains reusable controls and small compositions. A component
  may be a single module or a package with separate model, rendering, and
  interaction modules when those responsibilities are independently useful.
- `viewers/` and `workbenches/` are reserved for later reviewed migrations.
  They are not part of the current component move.

Consumers should import the narrow owning module under
`memcommit.adapters.console.tui` directly. `core` must not import components;
components may build on core. Operation labels, validation, provider work,
persistence, and Apply meaning remain with `commands/<operation>/` or the
operation's application owner rather than entering this package.

The rationale, migration boundary, and deferred Viewer/Workbench questions are
recorded in
`agent-records/docs/tui-component-architecture-design-rationale.md`.

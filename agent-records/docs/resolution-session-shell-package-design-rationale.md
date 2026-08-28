# Resolution Session shell package design rationale

## Motivation

The interface-owned Resolution Session shell combined two independently
understandable responsibilities in one 5,083-line module: read-only projection
and rendering, and the live prompt-toolkit runtime. The combined file made the
presentation contract difficult to inspect without also reading mutable
session state, key bindings, layout construction, and application lifecycle.

## Chosen boundary

`memcommit.adapters.console.terminal.components.resolution.session_shell` is now
a package with two implementation modules:

- `presentation.py` derives To Do guidance and renders reports, Viewer detail,
  Impact, review, and noninteractive snapshots.
- `runtime.py` owns the interactive entry point, process-local state, state
  transitions, terminal controls, key bindings, layout, and compact-shell
  delegation.

The package `__init__.py` preserves the former module import path and re-exports
the same callable and presentation surface. Runtime depends on presentation;
presentation does not depend on runtime or a live prompt-toolkit Application.

## Invariants

- This split changes source ownership only. It must not change visible text,
  focus topology, key behavior, draft handling, review policy, Apply authority,
  or returned `ResolutionWorkbenchAction` values.
- The canonical
  `memcommit.adapters.console.terminal.components.resolution.session_shell`
  import path is used directly by operation adapters and tests; no legacy
  console or interface facade remains.
- There is one implementation of every moved function. The package facade
  re-exports objects rather than wrapping or duplicating their behavior.
- `compact_shell.py` remains a sibling implementation and is still entered
  only through the existing runtime decision.

## Alternatives and limitations

Keeping a thin `session_shell.py` beside a differently named package would
preserve the same behavior but retain two physical concepts for one public
surface. Replacing the module with a package gives the public concept one
location without forcing caller migration.

The runtime intentionally remains closure-heavy in this change. Extracting a
typed Session State or Controller would change the internal execution model
and deserves separate behavior-preserving work after this coarse boundary is
stable. Private rendering helpers remain re-exported because the existing
console compatibility facade imports them; narrowing that surface is also a
separate migration.

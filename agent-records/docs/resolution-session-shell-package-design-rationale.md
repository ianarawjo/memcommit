# Resolution Session shell package design rationale

## Motivation

The interface-owned Resolution Session shell combined two independently
understandable responsibilities in one 5,083-line module: read-only projection
and rendering, and the live prompt-toolkit runtime. The combined file made the
presentation contract difficult to inspect without also reading mutable
session state, key bindings, layout construction, and application lifecycle.

## Chosen boundary

`memcommit.adapters.console.terminal.components.resolution.session_shell`
keeps pure presentation separate from a responsibility-oriented interactive
runtime:

- `presentation.py` derives To Do guidance and renders reports, Viewer detail,
  Impact, review, and noninteractive snapshots.
- `controller.py` owns process-local response, destination, review, and status
  state together with validated semantic action construction.
- `runtime.controls` creates live prompt-toolkit controls and their semantic
  navigation sections.
- `runtime.editors` owns response-draft and Save Location editor behavior.
- `runtime.review_flow` owns Items preview, final-review transitions, and
  semantic submission handoff.
- `runtime.keymap` contains responsibility-specific keyboard adapters:
  `keyboard_hints`, `focus_surfaces`, `navigation_bindings`,
  `surface_activation`, response and destination bindings, action shortcuts,
  and layered back navigation.
- `runtime.layout` constructs the peer-frame prompt-toolkit Application.
- `runtime.runner` validates configuration, composes the collaborators,
  delegates the compact shell, and owns the application lifecycle.

The shell and `runtime` package `__init__.py` files preserve the former module
import path by re-exporting the exact callable implemented by
`runtime.runner`. Runtime depends on presentation; presentation does not
depend on runtime or a live prompt-toolkit Application.

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
- Keymap modules adapt keys to the controller, editors, controls, and review
  flow; they do not duplicate editing, review, validation, or Apply meaning.
- `keyboard_hints` projects only available keyboard guidance. Status-message
  precedence remains part of the runner's footer composition.
- Moving state or event binding must not change visible text, focus order,
  draft durability, validation, decision-free policy, or returned actions.
- `compact_shell.py` remains a sibling implementation and is still entered
  only through the existing runtime decision.

## Alternatives and limitations

Keeping a thin `session_shell.py` beside a differently named package would
preserve the same behavior but retain two physical concepts for one public
surface. Replacing the module with a package gives the public concept one
location without forcing caller migration.

Keeping mutable state, controls, editors, review transitions, key bindings, and
layout in one runtime closure was rejected because prompt-toolkit mechanics
appeared to own review and action policy. Splitting by individual key was also
rejected: each keymap module instead owns one coherent interaction
responsibility. A frozen binding-state value shares existing owners between
those adapters without creating a second semantic state machine. Private
rendering helpers remain re-exported because current shell collaborators and
tests import them; narrowing that surface is a separate migration.

# Resolution Session shell package design rationale

## Motivation

The interface-owned Resolution Session shell combined two independently
understandable responsibilities in one 5,083-line module: read-only projection
and rendering, and the live prompt-toolkit runtime. The combined file made the
presentation contract difficult to inspect without also reading mutable
session state, key bindings, layout construction, and application lifecycle.

## Chosen boundary

`memcommit.adapters.console.terminal.components.resolution.session_shell` keeps
the interactive entry point separate from a responsibility-oriented
`presentation` package:

- `presentation.inspection` renders the Workbench list, individual issue
  Viewer, and noninteractive snapshot.
- `presentation.reporting` renders whole reports, seeded Compare/Meld reports,
  Impact, and Memory diffs.
- `presentation.progression` derives To Do guidance and renders the final
  review or Apply confirmation.
- `presentation.formatting` contains only pure text and display-cell formatting
  shared by more than one presentation responsibility.
- `controller.py` owns process-local response, destination, review, and status
  state together with validated semantic action construction.
- `runtime.controls` creates the live prompt-toolkit controls and projects the
  semantic sections those controls render and navigate.
- `runtime.editors` owns response-draft and Save Location editor behavior,
  including validation, persistence callbacks, and focus entry.
- `runtime.review_flow` owns Items preview, review entry and return, final
  action reconstruction, and submission handoff.
- `runtime.keymap.bindings` assembles the responsibility-specific binding
  groups without owning their operation semantics.
- `runtime.keymap.keyboard_hints` projects the keyboard interactions available
  from the current Surface, focus, and editing state.
- `runtime.keymap.focus_surfaces` owns dynamic Surface topology and boundary
  movement; `navigation_bindings` and `surface_activation` own movement keys
  and Enter activation respectively.
- `runtime.keymap.response_bindings`, `destination_bindings`, and
  `input_focus` adapt writable controls to their existing editor owners, while
  `action_shortcuts` and `back_navigation` own direct action and retreat keys.
- `runtime.layout` owns peer-frame stacking, focused-frame styling, and
  construction of the prompt-toolkit `Application` from prepared controls.
- `runtime.runner` is the interactive entry point. It validates configuration,
  composes the collaborators, delegates the compact shell, and owns the final
  application lifecycle.

The shell, `presentation`, and `runtime` package `__init__.py` files preserve
their former import surfaces by re-exporting the same callable and presentation
objects. In particular, both `session_shell.run_resolution_workbench_shell`
and `session_shell.runtime.run_resolution_workbench_shell` are the exact object
implemented by `runtime.runner`; neither facade wraps it. Runtime depends on
presentation; presentation does not depend on runtime or a live prompt-toolkit
Application. Reporting may consume the read-only progression projection so the
Report and To Do panes describe the same next action; progression never imports
reporting.

The live-shell dependency direction starts at `runtime.runner`, which composes
the controller and the runtime collaborators. Controls depend on the controller
and pure presentation projections; editors depend on controls; review flow
depends on controls and editors; keymap binds those existing behaviors; layout
only receives prepared controls. The package facade continues to expose the
runtime entry point rather than exposing these internal collaborators as a
second public API.

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
- Presentation dependency direction is formatting toward the responsibility
  modules, with reporting allowed to depend on progression's read-only action
  projection. Inspection and progression do not depend on reporting.
- `formatting.py` must not become a generic helper drawer. Navigation,
  response state, Impact semantics, and Apply policy remain with their owning
  responsibility even when they use common text-layout functions.
- Moving state or composition must not change visible text, focus order, draft
  durability, validation, decision-free policy, or returned actions. The
  controller never calls a provider or applies a mutation; it only validates
  and returns the same typed `ResolutionWorkbenchAction` boundary.
- `compact_shell.py` remains a sibling implementation and is still entered
  only through the existing runtime decision.

## Alternatives and limitations

Keeping a thin `session_shell.py` beside a differently named package would
preserve the same behavior but retain two physical concepts for one public
surface. Replacing the module with a package gives the public concept one
location without forcing caller migration.

Splitting every renderer or helper into its own file was rejected because it
would replace one large module with a navigation burden while obscuring the
three user-facing responsibilities: inspecting one item, reading the complete
report, and progressing toward a reviewed action. The remaining large render
functions may be decomposed within their owning module later, but this change
intentionally preserves their behavior before changing their internals.

Keeping every mutable cell, semantic projection, editor, review transition,
key binding, and layout decision inside one runtime closure was rejected
because it made prompt-toolkit mechanics appear to own review and action
policy. Replacing the shell wholesale with a new state machine was also
rejected: the controller and runtime collaborators retain the established event
ordering while giving each responsibility one physical owner. The keymap is a
package because focus topology, navigation, activation, writable inputs,
shortcuts, retreat behavior, and keyboard guidance change for different
reasons. It is not split by individual key: each module owns one coherent
interaction responsibility and delegates editing, review, and action meaning
to the existing runtime owner. Keyboard status messages remain in the runner's
footer composition; `keyboard_hints` emits only available keyboard guidance.
Private rendering helpers remain re-exported because current shell
collaborators and tests import them; narrowing that surface is a separate
migration.

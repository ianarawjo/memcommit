# Blank Ground runtime responsibility design rationale

## Problem

The blank-Ground `runtime.py` owned 2,707 lines and kept its session state,
provider-backed drafting turn, Context candidate selection, and prompt-toolkit
interaction in one 2,509-line closure. Proposal validation and read-only text
rendering were already separated, but the live runtime still made unrelated
changes share one file and hid which state was process-local rather than
durable.

## Selected layout

The historical `ground.shell.runtime` import is preserved as a package with a
thin public facade and four responsibility directories:

- `session/` owns validated startup, the explicit mutable session state, and
  terminal result projection. Durable mutation remains behind the injected
  Apply callback.
- `grounding_drafting/` owns the background bridge for one blocking interpreter
  call and freezes ASK or PROPOSE output before it gains UI authority.
- `context_selection/` owns typed candidate rows plus pure ordering, cursor,
  and selection rules. Its choices remain process-local hints and do not create,
  load, bind, or mutate a Context.
- `terminal_interaction/` owns Ground-specific pane activity and focus-ring
  mechanics. Its former 2,236-line `application.py` is now the compatibility
  package `application/`, whose live interaction is split into four named
  owners:
  - `workbench_view.py` builds and synchronizes panes, render projections,
    focus, and local list/table cursors.
  - `turn_controller.py` owns dialogue, direct-edit, Context-plan, exact
    approval, refinement, and exit transitions.
  - `keybindings.py` declares the prompt-toolkit conditions and maps terminal
    keys to the narrow view and controller operations.
  - `grounding_coordinator.py` owns the blocking interpreter bridge, thinking
    animation, response freezing, and publication of a completed draft turn.

`entry.py` remains the thin stable runtime facade. The nested application's
`entrypoint.py` constructs one shared `GroundShellState`, wires the four owners,
and runs prompt-toolkit. The historical
`runtime.terminal_interaction.application` import therefore still resolves,
but it no longer makes rendering, terminal grammar, application transitions,
and background provider work share one change surface.

## Invariants

- Existing imports of `ground.shell.runtime` and `run_ground_shell` continue to
  resolve to identical public objects.
- Existing patchable prompt-toolkit test seams remain available from the
  historical runtime facade and are resolved when the workbench is built.
- A provider response cannot directly author the approved argv; proposal
  freezing and exact-command construction remain in `proposal.py`.
- A directly edited Goal must still be preserved exactly by the provider turn.
- Context selection remains separate from Ground creation and cannot introduce
  a hidden Context mutation.
- Apply remains reachable only through the explicit frozen-command approval
  path, and an uncertain Apply failure is not automatically retried.
- Closing the shell makes a late background interpreter result observationally
  inert.

## Alternatives and limitations

Splitting every pane, editor, or key group into its own file would name more
mechanics but obscure the four lifecycle responsibilities. Keeping the live
application in one file would minimize movement but retain the mixed change
surface. The selected split deliberately permits dependency injection through
the small `entrypoint.py` composition root; it does not introduce a generic
framework or claim that blank creation and the physical workspace viewer share
one semantic controller.
Further extraction should follow a proven reusable terminal component rather
than a file-size target alone.

This record documents package ownership only. It does not classify the Ground
operation route or replace the authored operation evidence ledger.

# Ground shell package design rationale

## Problem

The blank-Ground terminal flow was physically owned by one 3,672-line
`ground.shell` module, while the persistent named-Ground flow was owned by one
3,211-line `ground.named_shell` module. Both combined three independently
meaningful boundaries: frozen proposal meaning, read-only presentation, and
the live prompt-toolkit runtime. The single modules obscured those boundaries
and made their 2,509-line and 2,158-line runtime closures appear to own proposal
validation and rendering as well.

## Selected layout

`memcommit.adapters.console.commands.ground.shell` and
`memcommit.adapters.console.commands.ground.named_shell` are now packages with
three implementation modules each:

- `proposal.py` owns the typed blank-Ground proposal, dialogue-response
  validation and freezing, locally constructed argv, and exact-command review
  value.
- `presentation.py` owns read-only rendering for Goal, Contexts, Rules,
  Memories, workspace, dialogue, and exact approval.
- `runtime.py` owns the live prompt-toolkit application, process-local session
  state, background interpreter turn, interaction grammar, and explicit Apply
  handoff.

The named package applies the same top-level boundary to a different lifecycle:

- `proposal.py` owns exact command contracts, freshness bindings, and
  operation-aware effect projection for an already saved Ground.
- `presentation.py` owns read-only Goal, Context, Rule, Memory, Fit, and review
  projections.
- `runtime/` preserves the historical `ground.named_shell.runtime` import path
  while separating the live lifecycle into its process-local state,
  workbench view, turn controller, prompt-toolkit key bindings, background Fit
  coordinator, and thin entry-point wiring.

The named runtime package uses the following focused ownership:

- `state.py` owns the process-local Ground, proposal, draft, editor, selection,
  placement, notification, conversation, and background-turn state. It does not
  provide another durable Ground store.
- `workbench_view.py` owns prompt-toolkit widgets, the five-pane layout, state
  projection, input hosting, focus movement, viewport alignment, and pane
  synchronization. Read-only text formatting remains in the outer
  `presentation.py`.
- `turn_controller.py` owns reload, dialogue interpretation, direct-edit and
  draft preparation, exact-command approval, Apply recovery, and the
  transition back to input.
- `keybindings.py` maps prompt-toolkit conditions and keys onto the view, turn,
  and Fit owners without becoming another Ground mutation path.
- `fit_coordinator.py` owns AUTO-FIT eligibility, frozen-session background
  execution, duplicate suppression, receipt publication, follow-up scheduling,
  and receipt-boundary close deferral.
- `entrypoint.py` validates terminal capability, wires the owners, constructs
  the Application, and returns the established shell result.

The dependency direction is runtime toward proposal and presentation, and
presentation toward proposal. Within the named runtime, state is the common
process-local dependency; the view projects it, the turn and Fit controllers
coordinate it through the view, key bindings route interaction to those
owners, and the entry point performs only wiring. Proposal construction does
not depend on the live terminal runtime. Each package `__init__.py` re-exports
its prior module surface so existing `ground.shell`, `ground.named_shell`, and
`ground.named_shell.runtime` imports continue to resolve. The named runtime
also retains the former patchable widget-factory and renderer test seams at
that compatibility surface; the workbench resolves those seams only when a
view is constructed.

## Invariants

- A dialogue provider may return only an ASK or structured PROPOSE response;
  it cannot author the command that is approved.
- The exact Ground Save Location and Goal are validated and frozen before
  review.  The command argv remains locally constructed.
- Apply remains available only through the existing explicit exact-command
  approval path.
- Named proposals remain bound to the exact Ground UID, revision, state digest,
  and Context versions supplied by the application adapter.
- The named runtime still reloads the saved Ground after each successful
  command; moving its contract does not create an alternate persistence path.
- The workbench view may mutate process-local selection, focus, and viewport
  state, but Ground mutation remains exclusively behind the turn controller's
  injected exact Apply callback. Fit receipt persistence remains behind its
  injected Fit runner.
- Pane text, focus topology, key bindings, background-turn behavior, and
  cancellation semantics are intentionally unchanged.

## Alternatives and limitations

Keeping one module preserved physical locality but hid the proposal trust
boundary.  Splitting only presentation from runtime would have placed proposal
freezing in either a rendering module or a live terminal module, neither of
which expresses its authority accurately.  The three-module package therefore
uses the smallest split that names all three responsibilities.

The first package extraction deliberately kept one named runtime module because
it minimized movement while establishing the proposal and presentation trust
boundaries. Once those boundaries were stable, retaining the 2,183-line
closure made prompt-toolkit mechanics, Ground turns, and Fit concurrency share
one change surface. The selected follow-up introduces one explicit mutable
state object and separates those runtime responsibilities without redesigning
their state machine.

This change does not consolidate the distinct blank and named lifecycles, make
runtime state durable, or introduce a second command/application service. The
turn controller and workbench view remain intentionally substantial because
they preserve the established interaction grammar; finer extraction should
follow demonstrated reusable mechanics rather than operation-local file-size
targets. Moving local closure definitions into named classes and functions
changes their introspection paths even though compatibility imports and
observable terminal behavior remain stable.

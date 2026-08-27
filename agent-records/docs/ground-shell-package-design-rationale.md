# Blank-Ground shell package design rationale

## Problem

The blank-Ground terminal flow was physically owned by one 3,672-line
`ground.shell` module.  That module combined three independently meaningful
boundaries: freezing untrusted dialogue output into an approvable proposal,
rendering the proposal and process-local draft panes, and running the live
prompt-toolkit session.  The single module obscured those boundaries and made
the 2,509-line runtime closure appear to own proposal validation and rendering
as well.

## Selected layout

`memcommit.adapters.console.commands.ground.shell` is now a package with three
implementation modules:

- `proposal.py` owns the typed blank-Ground proposal, dialogue-response
  validation and freezing, locally constructed argv, and exact-command review
  value.
- `presentation.py` owns read-only rendering for Goal, Contexts, Rules,
  Memories, workspace, dialogue, and exact approval.
- `runtime.py` owns the live prompt-toolkit application, process-local session
  state, background interpreter turn, interaction grammar, and explicit Apply
  handoff.

The dependency direction is runtime toward proposal and presentation, and
presentation toward proposal.  Proposal construction does not depend on the
live terminal runtime.  The package `__init__.py` re-exports the prior public
surface so existing `ground.shell` imports continue to resolve.

## Invariants

- A dialogue provider may return only an ASK or structured PROPOSE response;
  it cannot author the command that is approved.
- The exact Ground Save Location and Goal are validated and frozen before
  review.  The command argv remains locally constructed.
- Apply remains available only through the existing explicit exact-command
  approval path.
- Pane text, focus topology, key bindings, background-turn behavior, and
  cancellation semantics are intentionally unchanged.

## Alternatives and limitations

Keeping one module preserved physical locality but hid the proposal trust
boundary.  Splitting only presentation from runtime would have placed proposal
freezing in either a rendering module or a live terminal module, neither of
which expresses its authority accurately.  The three-module package therefore
uses the smallest split that names all three responsibilities.

This change does not redesign the runtime state machine.  `runtime.py` remains
large and closure-based; extracting an explicit Ground session controller is a
separate future change.  Moving definitions changes their introspection and
pickle module path even though imports through `ground.shell` and observable
terminal behavior remain compatible.

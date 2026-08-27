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

The named package applies the same boundary to a different lifecycle:

- `proposal.py` owns exact command contracts, freshness bindings, and
  operation-aware effect projection for an already saved Ground.
- `presentation.py` owns read-only Goal, Context, Rule, Memory, Fit, and review
  projections.
- `runtime.py` owns repeated provider turns, direct edits, Fit execution,
  command approval, application handoff, and Ground reload.

The dependency direction is runtime toward proposal and presentation, and
presentation toward proposal. Proposal construction does not depend on the
live terminal runtime. Each package `__init__.py` re-exports its prior module
surface so existing `ground.shell` and `ground.named_shell` imports continue to
resolve.

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
- Pane text, focus topology, key bindings, background-turn behavior, and
  cancellation semantics are intentionally unchanged.

## Alternatives and limitations

Keeping one module preserved physical locality but hid the proposal trust
boundary.  Splitting only presentation from runtime would have placed proposal
freezing in either a rendering module or a live terminal module, neither of
which expresses its authority accurately.  The three-module package therefore
uses the smallest split that names all three responsibilities.

This change does not redesign either runtime state machine. The runtime modules
remain large and closure-based; extracting explicit Ground session controllers
or consolidating the distinct blank and named lifecycles is a separate future
change. Moving definitions changes their introspection and pickle module path
even though imports through the package facades and observable terminal
behavior remain compatible.

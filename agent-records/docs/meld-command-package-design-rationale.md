# Meld command package design rationale

## Problem

`memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld.command` combined the Typer operand
contract, route selection, saved-session and provider orchestration, TUI
handoff, and terminal rendering in one 2,496-line module. The largest function,
`cmd`, also performed both option validation and the complete post-validation
workflow. This made the adapter's control boundary difficult to identify and
made presentation changes appear coupled to authority and persistence logic.

## Chosen boundary

The Meld adapter keeps its implementation owners directly under the operation
package rather than under a generic `command/` container:

- `entrypoint.py` owns the Typer signature, raw value collection, launcher
  dispatch, and translation of interpretation failures to CLI usage errors.
- `interpretation.py` owns option conflicts, operand and scope normalization,
  one current-Context snapshot, and construction of a canonical
  `InterpretedMeldCommand`.
- `workflow/workflow.py` owns source and target binding checks, authorization,
  saved session state, provider and application-service delegation, TUI
  handoff, and Apply/defer execution.
- `presentation.py` owns session and receipt rendering, wait-screen projection,
  picker projection, and all terminal outcome messages.

`errors.py` contains only the shared user-facing exception so that presentation
does not need to depend on workflow. The dependency direction is entrypoint to
interpretation and workflow, workflow to presentation and the application
layer, and the thin `command.py` compatibility facade to those owners.
Presentation does not import entrypoint or workflow.

## Compatibility invariants

The import path `memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld.command` remains a
thin module facade that re-exports every prior top-level command function.
Assignments to historical integration and test seams are forwarded to the
submodule that owns the name, preserving callers that replace provider,
picker, TUI, or helper functions on the old module object. The outer Meld
package remains a lazy `cmd`-only composition surface, and runtime modules do
not import back through either facade.

The CLI operands, validation ordering, session formats, provider boundaries,
authorization checks, output text, and TUI behavior are intentionally
unchanged. `MeldCommandRequest` and `InterpretedMeldCommand` are process-local
console values; neither is a persisted schema or an application-layer command
model.

## Alternatives and limits

A two-file split between presentation and everything else would leave route
validation coupled to execution. Moving the Typer command into the application
layer would reverse the adapter dependency and duplicate existing Meld
application services. A deeper operation-level workflow decomposition may be
useful later, but this change deliberately establishes only the three coarse
boundaries before smaller concepts are extracted.

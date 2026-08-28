# Meld command package design rationale

## Problem

`memcommit.adapters.console.commands.meld.command` combined the Typer operand
contract, route selection, saved-session and provider orchestration, TUI
handoff, and terminal rendering in one 2,496-line module. The largest function,
`cmd`, also performed both option validation and the complete post-validation
workflow. This made the adapter's control boundary difficult to identify and
made presentation changes appear coupled to authority and persistence logic.

## Chosen boundary

The historical module is now a package with three responsibility owners:

- `entrypoint.py` owns the Typer signature, option-conflict validation, launcher
  routes, and construction of a normalized `MeldCommandRequest`.
- `workflow.py` owns source and target binding checks, authorization, saved
  session state, provider and application-service delegation, TUI handoff, and
  Apply/defer execution.
- `presentation.py` owns session and receipt rendering, wait-screen projection,
  picker projection, and all terminal outcome messages.

`errors.py` contains only the shared user-facing exception so that presentation
does not need to depend on workflow. The dependency direction is entrypoint to
workflow and presentation, and workflow to presentation and the application
layer. Presentation does not import entrypoint or workflow.

## Compatibility invariants

The import path `memcommit.adapters.console.commands.meld.command` remains a
facade that re-exports every prior top-level command function. Assignments to
historical integration and test seams are forwarded to the submodule that owns
the name, preserving callers that replace provider, picker, TUI, or helper
functions on the old module object. Runtime modules do not import back through
the facade.

The CLI operands, validation ordering, session formats, provider boundaries,
authorization checks, output text, and TUI behavior are intentionally
unchanged. `MeldCommandRequest` is process-local normalization; it is not a new
persisted schema or an application-layer command model.

## Alternatives and limits

A two-file split between presentation and everything else would leave route
validation coupled to execution. Moving the Typer command into the application
layer would reverse the adapter dependency and duplicate existing Meld
application services. A deeper operation-level workflow decomposition may be
useful later, but this change deliberately establishes only the three coarse
boundaries before smaller concepts are extracted.

# Meld command interpretation design rationale

## Problem

Meld's CLI grammar was previously split between the Typer entrypoint and the
console workflow.  The entrypoint classified `--to` with derived booleans such
as `to_is_symmetric` and rejected some cross-option combinations, while
`execute_meld_command` later reconstructed the directional or symmetric
meaning, resolved operands, and built the canonical start command.  The raw
arguments and their derived classifications traveled together in
`MeldCommandRequest`, so a direct caller could construct a contradictory value
even though normal Typer composition did not.

The split also made the workflow discover the command's meaning before it
could begin its actual saved-state routing.  This obscured the boundary between
CLI spelling and Meld's operation contracts.

## Selected boundary

`memcommit.adapters.console.commands.meld.interpretation` is the sole
owner of Meld CLI form interpretation.  The console path is now:

```text
Typer entrypoint
  -> raw MeldCommandRequest
  -> interpret_meld_command
  -> InterpretedMeldCommand or a typed launcher route
  -> workflow saved-state dispatch
  -> application Start, Restart, turn, or Apply contract
```

The entrypoint owns Typer declarations, raw value collection, and translation
of interpretation failures into usage exit status 2.  Interpretation owns:

- scope-preset and explicit descendant normalization;
- mutual exclusion and dependency rules among CLI options;
- the overloaded role of `--to`;
- positional, `--from`, `--into`, and inline-Memory forms;
- one command-start current-Context snapshot;
- existing-Context locator resolution and inline operand classification;
- canonical source, target, action, and restart-command meaning; and
- typed distinction between bare setup, saved-session browsing, and an
  executable non-launcher command.

The workflow receives no raw positional aliases and no derived
`to_is_symmetric`, `directional_to`, or `action_count` fields.  It owns only
state-dependent routing: authority checks, target and session discovery,
Start versus Restart versus existing-session action, provider wait
presentation, and final outcome presentation.  Application requests retain
their independent terminal-neutral invariants and remain fail-closed if a
non-CLI adapter supplies an invalid operation request.

## Invariants

- Every relative existing-Context operand is resolved from the same captured
  current Context.  Bare names remain canonical global names.
- A symmetric Result may be new, so its exact requested name is not passed
  through the existing-Context locator resolver.
- Interpretation may read the current Context name and use Context existence
  to disambiguate an operand, but it must not load a Meld session, connect a
  provider, publish a Context, or mutate durable state.
- The interpreted value contains canonical names and one typed action.  Raw
  flags and an independently supplied derived classification cannot disagree.
- Existing command spellings, errors, exit categories, scope defaults, and
  canonical user-visible restart commands remain compatible.

## Alternatives considered

Keeping classification in the entrypoint was rejected because the workflow
would still need to understand the same overloaded grammar.  Moving the CLI
grammar into application Start requests was rejected because `--to`,
`--into`, positional arity, and bare TTY launch behavior are console adapter
concerns rather than operation semantics.

A generic cross-operation `invocation` layer was also rejected.  The retired
console invocation prototype never owned a shipped command and introduced a
parallel route model.  This boundary is deliberately operation-specific and
is named command interpretation to describe its concrete consumer and
contract.

## Intentional limitations

This change does not reorganize the remaining workflow, consolidate its
source-binding helpers with the canonical application runtime, split semantic
turn orchestration, or divide Start, Restart, and existing-session action
controllers.  Those are separate boundaries whose behavior should be reviewed
after the CLI grammar owner is stable.

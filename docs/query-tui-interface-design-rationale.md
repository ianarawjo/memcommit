# Query TUI interface-ownership rationale

Last verified: 2026-08-15.

## Problem

Query execution had moved below the terminal boundary, but its 1,200-line
workbench still lived in `memcommit.commands.query_workbench`. That module mixed
process-local values, typed answer projection, and prompt-toolkit mechanics, and
it depended on several operation-neutral helpers through command-owned paths.
The result was callable without the CLI, but its ownership still implied that
the command layer implemented the TUI.

## Decision

The Query terminal interface now owns three explicit modules:

```text
memcommit/interfaces/tui/operations/query/
  model.py    process-local transcript, response, receipt, and runner types
  adapter.py  typed answer/reference/transcript and clipboard projections
  screen.py   prompt-toolkit layout, focus, keys, and background-turn lifecycle
```

The command imports this package directly. The former
`memcommit.commands.query_workbench` path contains only object-identical
compatibility exports.

The screen also uses interface-owned background-turn, horizontal-choice,
activity-animation, and plain-text clipboard components. Their old command
paths remain compatibility exports for consumers that have not migrated yet;
there is one implementation for each mechanic.

Session Help is intentionally injected by the command composition edge. The
Help controller still freezes Typer's root command inventory, so making the TUI
import it would reverse the interface-to-command dependency. The Query screen
accepts an optional binder, production supplies the established Session Help
binder, and isolated screen tests may supply a deterministic fake.

## Preserved contracts

- No provider is constructed before explicit Query submission.
- Ordinary, granted, and saved-transcript modes retain the same Source, scope,
  session, authority, and disclosure behavior.
- Background close waits for the frozen read-only turn and publishes no partial
  answer.
- Answer body and Reference focus, scrolling, `y` focused copy, `Y` complete
  copy, nonfatal clipboard failure, and read-only exit behavior are unchanged.
- The command still owns Store/catalog composition and error handling; this
  slice does not move the overloaded CLI selector grammar.

## Verification

Architecture tests reject command imports from the Query TUI package, require
the production command to import the interface owner, and prove compatibility
exports are object-identical and implementation-free. Query workbench and
shared-component regressions cover the same direct calls through the new path.

The ordered `docs/screenshots/query-find-clipboard-20260813/` 180×52 PTY trace
was regenerated through the new Query screen. It records entry, question input,
answer-body and Reference focus, focused and complete copy, adapter failure,
close, and read-only verification. The path move itself introduces no new
visible state.

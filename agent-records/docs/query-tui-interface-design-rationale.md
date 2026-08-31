# Query workbench ownership rationale

Last verified: 2026-08-28.

## Problem

An earlier interface extraction placed Query-specific models, projections, and
prompt-toolkit composition under `interfaces/tui/operations/query`, while
`commands/query/workbench.py` remained as an object-identity compatibility
facade. As the console adapters became operation packages, that arrangement
left the command importing a generic interface owner and kept a backwards
facade at the location that should own Query's terminal composition. The
operation-neutral controls were already shared independently, so the extra
operation interface layer no longer expressed a useful boundary.

## Decision

The Query command package now owns four explicit workbench modules:

```text
memcommit/adapters/console/commands/search_explain/retrieve_answer/query/workbench/
  model.py         process-local response, result, clipboard, and runner types
  presentation.py  typed Answer/Reference and clipboard projections
  scope.py         QUERY-granted View selection and federation control
  screen.py        prompt-toolkit layout, focus, keys, and background-turn lifecycle
```

The command imports this package directly. The former flat workbench facade and
`interfaces/tui/operations/query` package are removed without compatibility
facades. `commands/query/presentation.py` remains the separate non-interactive
answer owner.

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
- Each Reference focus stop now presents and copies one compact logical row in
  `[N] content — UID prefix, Context alias` order. The Context remains inside
  every row because adjacent References may identify different Sources.
- The command still owns Store/catalog composition and error handling; this
  slice does not move the overloaded CLI selector grammar.

## Verification

Architecture tests reject dependencies on foreign command implementations,
require the production command to import its workbench owner directly, verify
the four-module package, and prove the retired interface contains no Python
facade. Query workbench and shared-component regressions cover the same direct
calls through the new path.

The refreshed ordered `agent-records/docs/screenshots/query-tui-interface-20260815/` 180×52
PTY trace was generated through the Query screen. It records entry, question
input, compact answer-body and Reference focus, focused and complete copy,
adapter failure, close, and read-only verification. The ownership move itself
introduced no new state or visible behavior, so the ordered images do not need
to be regenerated; their capture scripts now import the canonical workbench.

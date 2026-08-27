# Contexts Application Boundary Matrix

## Reviewed operation

`mem contexts` is a read-only orientation operation. It freezes the current
Context name, local names, and effectively READ-granted public names into one
hierarchically ordered catalog, then renders that typed result without opening
Context content or changing the current pointer.

| Concern | Owner | Boundary |
| --- | --- | --- |
| Row and catalog result types | `memcommit.application.operations.contexts.application` | Terminal-free immutable values |
| Store/Profile snapshot and Grant projection | `memcommit.application.operations.contexts.runtime` | Read-only local-plus-Grant catalog |
| ANSI styling and text output | `memcommit.commands.contexts.command` | Typer presentation only |

## Invariants

- The current marker and catalog use one command-local current-name snapshot.
- Public names determine hierarchy; Grant attachment metadata is never a tree
  edge.
- The nearest lexical Grant supplies the exact authority profile and
  capability annotation for a projected public name.
- Context records are not opened and no provider, cache, session, checkpoint,
  or mutation route is entered.
- Plain and interactive invocations receive the same ordered rows; color is
  not an information channel.

## Compatibility boundary

The existing empty-local-store behavior is retained: without any ordinary
local Context, the command prints its established initialization guidance
instead of becoming a Profile-wide Grant browser. Profile-wide source
selection remains owned by the controls that explicitly promise `PROFILE` or
`ALL READABLE CONTEXTS` breadth.

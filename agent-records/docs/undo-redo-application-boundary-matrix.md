# Undo and Redo Application Boundary Matrix

## Reviewed operations

`mem undo` and `mem redo` are distinct operation adapters over one shared
command-restoration selector. Each restores exactly one globally ordered
checkpoint-producing command unit and returns the existing typed
`CommandRestoreResult` for presentation.

| Concern | Owner | Boundary |
| --- | --- | --- |
| Granted-versus-local stack selection | `memcommit.application.operations.restoration.runtime` | Shared fail-closed restoration mechanic |
| Undo direction | `memcommit.application.operations.undo.runtime` | Fixed `undo` adapter |
| Redo direction | `memcommit.application.operations.redo.runtime` | Fixed `redo` adapter |
| Receipt rendering | `memcommit.adapters.console.coordination.restoration_present` | Shared presentation only |
| CLI errors and syntax | `memcommit.adapters.console.commands.undo.command`, `memcommit.adapters.console.commands.redo.command` | Typer adapters |

## Invariants

- A staged granted Update is considered only when its durable status can
  participate in the requested direction.
- The active Profile's ordinary command stack is used when no eligible granted
  receipt exists.
- A granted route falls back to the ordinary stack only when the authority
  reports the exact empty-stack condition for that direction.
- Revocation, authority drift, ordering failure, and every nonempty-stack error
  remain fail-closed.
- Undo and Redo retain distinct operation identities in checkpoints, History,
  Trace, and terminal receipts even though route selection is shared.

## Deliberate boundary

The shared core selects a restoration authority; it does not merge the two
operations or invent a generic user-facing command. The Store and granted
Update application continue to own checkpoint reconstruction, locks, CAS,
rollback, and companion-artifact restoration.

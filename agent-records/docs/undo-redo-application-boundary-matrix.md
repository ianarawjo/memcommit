# Undo and Redo Application Boundary Matrix

## Reviewed operations

`mem undo` and `mem redo` are distinct operation adapters over one shared
command-restoration selector. Each restores exactly one globally ordered
checkpoint-producing command unit and returns the existing typed
`CommandRestoreResult` for presentation.

| Concern | Owner | Boundary |
| --- | --- | --- |
| Command-unit model and stack reconstruction | `memcommit.application.capabilities.command_recovery.model`, `stack_reconstruction` | Recover one safe Profile-global LIFO order from retained checkpoint evidence |
| Granted-versus-local stack selection | `memcommit.application.capabilities.command_recovery.execution` | Shared fail-closed restoration capability |
| Undo direction | `memcommit.application.operations.history_recovery.recovery.undo.runtime` | Fixed `undo` adapter |
| Redo direction | `memcommit.application.operations.history_recovery.recovery.redo.runtime` | Fixed `redo` adapter |
| Receipt rendering | `memcommit.adapters.console.terminal.components.restoration_receipt` | Shared presentation only |
| CLI errors and syntax | `memcommit.adapters.console.commands.history_recovery.recovery.undo.command`, `memcommit.adapters.console.commands.history_recovery.recovery.redo.command` | Typer adapters |

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
- Revert owns its typed request, Store binding, and direct/recursive
  checkpoint-unit execution under `memcommit.application.operations.history_recovery.recovery.revert`.
  It does not join the command-stack direction selector used by Undo/Redo.

## Deliberate boundary

The shared capability reconstructs command units and selects an Undo/Redo
restoration authority; it does not execute Revert or invent a generic
user-facing command. Each operation retains its own application package. The
Store and granted Update application continue to own locks, CAS, rollback, and
companion-artifact restoration.

# Clear Application Boundary Matrix

## Reviewed operation

`mem clear` removes every direct item from one exact Context or from a frozen
local lexical subtree. Invocation is the approval boundary because publication
creates an Undoable command checkpoint; the retained hidden `--force` flag is
syntax compatibility only.

| Concern | Owner | Boundary |
| --- | --- | --- |
| Request and durable/no-change result | `memcommit.application.operations.clear.application` | Terminal-independent typed contract |
| Context resolution and authority | `memcommit.application.operations.clear.runtime` | One captured current name and exact `ContextAccess` |
| Recursive catalog freeze and atomic save | `memcommit.application.operations.clear.runtime` | Complete local subtree or no publication |
| Error and receipt rendering | `memcommit.commands.clear.command` | Typer-only adapter |

## Invariants

- Exact Clear requires DELETE and publishes one Context save.
- Recursive Clear is local-only and fails before mutation if a readable Grant
  is lexically below the selected public root.
- Empty subtree members remain digest-bound even though they need no
  checkpoint, preventing a concurrent add from escaping the frozen command.
- Changed subtree members publish through one command batch and Undo/Redo as a
  single unit.
- Embedded Contexts and lexical descendants remain independent axes: recursive
  Clear follows only local public-name descendants and clears only direct
  items.

## Deliberate boundary

The command captures current Context identity once and passes it to the
runtime. It retains only argument syntax and terminal presentation; Store,
authority, CAS, checkpoint, and rollback behavior have no dependency on Typer.

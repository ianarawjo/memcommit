# Chunk Application Boundary Matrix

## Reviewed operation

`mem chunk` mechanically replaces one directly owned Memory, or every
splittable direct Memory in one Context, with ordered child Memories. The CLI
invocation is the approval boundary and the publication is one Undoable
checkpoint-producing command unit.

| Concern | Owner | Boundary |
| --- | --- | --- |
| Text boundaries and size limits | `memcommit.operations.chunk.domain` | Pure text in, ordered text chunks out |
| Direct-Memory resolution and child construction | `memcommit.operations.chunk.application` | Frozen in-memory Context, no Store or terminal |
| Authority revalidation, replacement, checkpoint, save | `memcommit.operations.chunk.runtime` | One CREATE+DELETE authorized save or no publication |
| Operand discovery, preview, receipt | `memcommit.commands.chunk` | Typer-only adapter around the operation package |
| Historical Python import | `memcommit.chunking` | Identity alias to the operation-owned domain |
| Historical in-memory call | `memcommit.ops.chunk` | Thin lazy adapter to the application function |

## Invariants

- Context scope remains direct-only; lexical descendants, Embeds, and
  References are not traversed.
- A split replaces its exact Source UID in place and records every replacement
  UID so Trace never infers lineage from repeated content.
- CREATE and DELETE are revalidated together immediately before the single
  save.
- Empty and one-piece plans publish nothing.
- The compatibility module contains no second implementation.

## Deliberate boundary

Target discovery still belongs to the CLI adapter because its auto-typed
operand grammar is presentation-specific. The application accepts an already
loaded Context, while the runtime accepts the exact authority-bearing
`ContextAccess`; neither reads argv or terminal state.

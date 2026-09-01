# Compact exact-Memory Reference — 2026-08-31

This ordered capture records bare `mem reference` as one compact, input-first
exact-Memory flow. The persistent setup has no mode selector: it asks for one
existing local `TARGET CONTEXT`, then one exact Memory under an explicitly
qualified local or READ-granted owner. Context-wide direct/recursive snapshots
remain available through explicit CLI operands and are intentionally absent
from this bare interactive launcher.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Command: bare `mem reference`
- Exact command: `mem reference MEMORY --from shared/source --into workspace`
- Profile/current Context: active `authoring` Profile; current local Context
  `workspace`; one managed authority Source published as `shared/source`
- Grant: exact `READ` permission; QUERY-only rows are not eligible
- PTY: `180` columns × `52` rows, verified inside every cumulative capture
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, true-color prompt-toolkit
  output, and `NO_COLOR` removed
- Buffer: the compact form stays in the terminal's main buffer; the harness
  rejects an alternate-screen transition
- CLI harness: the actual Reference and Show Typer adapters are registered in
  a focused command group so unrelated command-package imports cannot affect
  this operation-specific record
- Renderer: actual ANSI PTY bytes replayed through `pyte`; every PNG has a
  matching cumulative `.typescript` and final-canvas `.txt`

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-target-context` | launch | local `TARGET CONTEXT` owns focus; `SOURCE MEMORY` exposes `BROWSE CONTEXT` and `CHOOSE MEMORY`; proposed command is invalid | fixture only |
| `02-exact-memory-owner` | `Down` | `SOURCE MEMORY` owner/locator field shows the explicit `shared/source` Grant with READ/REFERENCE annotation | none |
| `03-exact-memory-choices` | `Enter`, `Enter` | transient choices use the shared one-line `[memory UID] preview` row and contain directly owned Memories only; no whole-Context row is offered | none |
| `04-exact-memory-selected` | `Enter` | the field becomes canonical `shared/source:FULL_UID`, the exact Memory is staged, and the proposed command becomes runnable | none |
| `05-proposed-command-enter` | `Down` | `PROPOSED COMMAND · ENTER TO PROCEED` owns focus; there is no separate Run action | none |
| `06-success-receipt` | `Enter` | Freeze revalidates Source/Grant/Memory/Target and Apply prints the established `Referenced snapshot …` receipt | one snapshot Reference and one Target checkpoint |
| `07-read-only-verification` | `Enter` at capture gate | `mem show` reads the retained bytes and the harness verifies public Source, exact Memory, Reference, Grant, and read-only snapshot identity | none |

The Source Memory row accepts an owner Context, a UID/prefix inside its retained
owner, or the shared `CONTEXT:UID` spelling. Choosing from the list writes the
canonical `CONTEXT:FULL_UID` locator back into the same field. A bare UID never
scans other readable or granted Contexts, while an explicit qualified locator
may move both owner and Memory together. The proposed command remains editable
in place; only a complete command that round-trips into the same
Target/owner/Memory controls can proceed.

Reproduce from the repository root with:

```sh
python agent-records/docs/screenshots/reference-compact-exact-memory-20260831/capture.py
```

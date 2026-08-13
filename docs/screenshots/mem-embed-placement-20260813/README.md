# `mem embed` ordered placement capture log

These images render the actual color-preserving PTY stream produced by the
flagless `mem embed` command. The main path chooses a Child and a non-current
Into Context, hovers and stages the gap between its first and second Memories,
reviews the exact `--before` command, applies it, and verifies the persisted
direct-item order with the real `mem show` command. Separate disposable runs
cover cancellation and self-Embed rejection.

## Reproduction frame

- Command: `mem embed`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before launch and verified inside every
  child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile/current Context: disposable local store; current `guide`
- Local catalog: `archive`, `examples`, and `guide`
- Main relationship: `examples → archive`
- Placement: between Archive's first and second directly owned Memories
- Renderer: each cumulative ANSI stream is replayed with `pyte`, drawn at
  `1980×1092` with DejaVu Sans Mono, and retained as matching `.typescript`,
  `.txt`, and `.png` files
- Durable scope: temporary stores removed after capture; no real Context,
  checkpoint, or current-Context pointer was changed

The capture command was:

```bash
env -u NO_COLOR TERM=xterm-256color COLORTERM=truecolor \
  python docs/screenshots/mem-embed-placement-20260813/capture.py
```

The driver fails unless all three child streams report `180x52`, contain ANSI
control sequences and foreground styles, the cancellation run confirms
byte-semantic equality for every Context, and the rejected self-Embed can close
without mutation.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation in disposable store |
| --- | --- | --- | --- |
| `01-setup-entry.png` | Launch `mem embed` | Child selector initially checks `archive`; the combined `INTO + POSITION` frame checks current `guide`, expands its real direct Memory under that row, and shows one checked `LAST · DEFAULT` line | None |
| `02-child-selected.png` | `Down`, `Enter` | `examples` is the retained Child while the cursor and checked row remain distinguishable | None |
| `03-target-selected.png` | `Tab`, `Up`, `Up`, `Enter` | `archive` is retained in the shared target tree; its three direct Memories and one checked `LAST · DEFAULT` line expand under that same row | None; current remains `guide` |
| `04-gap-hover.png` | `Tab`, `Up`, `Up` | The selector's one position line moves between the first and second Memories, while `LAST` remains staged and the exact append command is unchanged | None |
| `05-gap-staged.png` | `Enter` | That single middle line becomes checked; exact review changes to `--before` the second full UID | None |
| `06-exact-command.png` | `Tab` | `TO DO · EXACT COMMAND` is focused and names the canonical Child, target, full adjacent UID, one-target mutation, live-reference boundary, and exact gap | None |
| `07-success-receipt.png` | `Enter` | The TUI closes and the command receipt confirms `examples` was embedded between the two displayed neighbor prefixes | One target save and one Embed checkpoint; this is the first durable mutation |
| `08-read-only-verification.png` | `Enter` at the capture-only pause | Actual `mem show --context archive` lists Memory 1, embedded `examples`, Memory 2, Memory 3 in persisted Context order; current remains `guide` | None after Embed |
| `09-cancelled.png` | Separate launch, then `Escape` | Cancellation receipt, all Contexts unchanged, and current still `guide` | None |
| `10-self-embed-rejected.png` | Separate launch; `Down`, `Down`, `Enter`, then Tab through the combined target/Position frame and activate To Do | Child and Into are both `guide`; the exact command stays unrun and the footer rejects self-Embed | None; the driver then cancels and confirms every Context is unchanged |

The pause between `07` and `08` exists only so the success receipt and the
read-only verification are independently reconstructable. It is not part of
the product flow.

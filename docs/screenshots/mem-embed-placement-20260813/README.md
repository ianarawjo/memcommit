# `mem embed` ordered placement capture log

These images render the actual color-preserving PTY stream produced by the
flagless `mem embed` command. The entry first chooses a typed live-link mode.
The Context path chooses a Child and a non-current Into Context, stages a gap,
reviews the exact command, applies it, and verifies the persisted direct-item
order. The Memory path chooses one directly owned ordinary Memory, reuses the
same placement/review mechanics, and verifies the resulting live link with the
real `mem show` command. Separate disposable runs cover cancellation and
self-Embed rejection.

## Reproduction frame

- Command: `mem embed`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before launch and verified inside every
  child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile/current Context: disposable local store; current `guide`
- Local catalog: `archive`, `examples`, and `guide`
- Context relationship: `examples → archive`
- Memory relationship: first direct Memory in `archive → guide`
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
| `01-setup-entry.png` | Launch `mem embed` | `LINK TYPE` initially checks `CONTEXT`; the Child selector checks `archive`, and `INTO + POSITION` checks current `guide` with one checked `LAST · DEFAULT` gap | None |
| `02-child-selected.png` | `Tab`, `Down`, `Enter` | `examples` is the retained Child while the cursor and checked row remain distinguishable | None |
| `03-target-selected.png` | `Tab`, `Up`, `Up`, `Enter` | `archive` is retained in the shared target tree; its three direct Memories and one checked `LAST · DEFAULT` line expand under that same row | None; current remains `guide` |
| `04-gap-hover.png` | `Tab`, `Up`, `Up` | The selector's one position line moves between the first and second Memories, while `LAST` remains staged and the exact append command is unchanged | None |
| `05-gap-staged.png` | `Enter` | That single middle line becomes checked; exact review changes to `--before` the second full UID | None |
| `06-exact-command.png` | `Tab` | `TO DO · EXACT COMMAND` is focused and names the canonical Child, target, full adjacent UID, one-target mutation, live-reference boundary, and exact gap | None |
| `07-success-receipt.png` | `Enter` | The TUI closes and the command receipt confirms `examples` was embedded between the two displayed neighbor prefixes | One target save and one Embed checkpoint; this is the first durable mutation |
| `08-read-only-verification.png` | `Enter` at the capture-only pause | Actual `mem show --context archive` lists Memory 1, embedded `examples`, Memory 2, Memory 3 in persisted Context order; current remains `guide` | None after Embed |
| `09-cancelled.png` | Separate launch, then `Escape` | Cancellation receipt, all Contexts unchanged, and current still `guide` | None |
| `10-self-embed-rejected.png` | Separate launch; `Tab`, `Down`, `Down`, `Enter`, then Tab through the target/Position frame and activate To Do | Child and Into are both `guide`; the exact command stays unrun and the footer rejects self-Embed | None; the driver then cancels and confirms every Context is unchanged |
| `11-memory-mode.png` | Separate launch, then `Right` | `LINK TYPE` checks `MEMORY`; the Child frame is replaced by the shared direct-Memory Source picker | None |
| `12-memory-selected.png` | `Tab`, `Down`, `Enter` | The first directly owned `archive` Memory is explicitly checked; the exact command contains its full UID and `--from archive` | None |
| `13-memory-target.png` | `Tab` | Current `guide` remains the reviewed local Target and its existing direct Memory stays visible | None |
| `14-memory-position.png` | `Tab` | The common placement layer owns the checked append gap independently of the Source picker | None |
| `15-memory-exact-command.png` | `Tab` | To Do shows the full Memory UID, `--from`, Target, stable adjacent UID, one-Target effect, and live ownership boundary | None |
| `16-memory-success-receipt.png` | `Enter` | The TUI closes and the receipt identifies the Source Memory, Source Context, new Embed UID, Target, and exact gap | One Target save and one Embed checkpoint |
| `17-memory-read-only-verification.png` | `Enter` at the capture-only pause | Actual `mem show --context guide` renders the original Memory followed by `[embedded memory]`, its Source identity, `READ ONLY`, and current Source content | None after Embed |

The pause between `07` and `08` exists only so the success receipt and the
read-only verification are independently reconstructable. It is not part of
the product flow.

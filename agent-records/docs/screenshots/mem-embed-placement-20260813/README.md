# `mem embed` ordered placement capture log

These images render the actual color-preserving PTY stream produced by the
flagless `mem embed` command. The entry first chooses a typed live-link mode.
The Context path chooses a Child and a non-current Into Context, stages a gap,
reaches the always-editable exact command, types into it, synchronizes the
changed Child, Target, and placement back to the upper controls live, applies
it with one explicit Enter, and verifies the persisted direct-item order. The
Memory paths first select the current Target's own Memory and defer self-link
rejection to the exact action, then choose a peer-owned ordinary Memory and
verify the resulting live link with the real `mem show` command. Separate
disposable runs cover cancellation, self-Embed rejection, and invalid
command-form input.

## Reproduction frame

- Command: `mem embed`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before launch and verified inside every
  child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile/current Context: disposable local store; current `guide`
- Local catalog: `archive`, `examples`, and `guide`
- Initial Context relationship: `examples → archive`
- Final synchronized Context relationship: `archive → guide`
- Reviewed rejected Memory relationship: first direct Memory in `guide → guide`
- Applied Memory relationship: first direct Memory in `archive → guide`
- Initial placement: between Archive's first and second directly owned Memories
- Final Context placement: append after Guide's existing direct Memory
- Renderer: each cumulative ANSI stream is replayed with `pyte`, drawn at
  `1980×1092` with DejaVu Sans Mono, and retained as matching `.typescript`,
  `.txt`, and `.png` files
- Durable scope: temporary stores removed after capture; no real Context,
  checkpoint, or current-Context pointer was changed

The capture command was:

```bash
env -u NO_COLOR TERM=xterm-256color COLORTERM=truecolor \
  python agent-records/docs/screenshots/mem-embed-placement-20260813/capture.py
```

The driver fails unless all six child streams report `180x52`, contain ANSI
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
| `05-gap-staged.png` | `Enter` | That single middle line becomes checked; exact review changes to `--before` the second item's collision-safe seven-character prefix | None |
| `06-exact-command.png` | `Tab` | The small blue `COMMAND · RUNNABLE` box keeps `mem embed` as a fixed prompt and exposes only canonical Child, Target, and collision-safe adjacent-selector arguments for editing | None |
| `06a-command-invalid-live.png` | `Ctrl-U`, type incomplete `archive --into` arguments | `Ctrl-U` clears only arguments; the fixed `mem embed` prompt remains, the box turns red, Enter is blocked, and the prior upper controls remain checked | None |
| `06b-command-live-synced.png` | `Ctrl-U`, type complete `archive --into guide` arguments; no Enter | As soon as the arguments become valid, the box returns to blue, upper Child changes to `archive`, Target changes to `guide`, and append becomes checked | None |
| `07-success-receipt.png` | `Enter` | The one explicit approval closes the TUI and confirms `archive` was embedded after Guide's existing Memory | One target save and one Embed checkpoint; this is the first durable mutation |
| `08-read-only-verification.png` | `Enter` at the capture-only pause | Actual `mem show --context guide` lists its Memory followed by embedded `archive`; current remains `guide` | None after Embed |
| `09-cancelled.png` | Separate launch, then `Escape` | Cancellation receipt, all Contexts unchanged, and current still `guide` | None |
| `10-self-embed-rejected.png` | Separate launch; `Tab`, `Down`, `Down`, `Enter`, then Tab through the target/Position frame and activate To Do | Child and Into are both `guide`; the exact command stays unrun and the footer rejects self-Embed | None; the driver then cancels and confirms every Context is unchanged |
| `10a-command-edit-rejected.png` | Separate launch; reach the editable field, replace its arguments with `examples --into missing`, then press `Enter` | The fixed `mem embed` prefix remains; the compact box stays red, reports that `missing` is outside the frozen Target catalog, blocks Enter, and retains the initial upper values | None; one Escape cancels and every Context is verified unchanged |
| `10b-memory-current-source.png` | Separate launch, then `Right` | `MEMORY` mode initially opens current Target `guide` as Source and immediately shows its directly owned Memory | None |
| `10c-same-context-memory-selected.png` | `Tab`, `Down`, `Enter` | The exact `guide` Memory is checked even though `guide` is also the Target; the editable command retains `--from guide --into guide` as valid process-local review state | None |
| `10d-same-context-target.png` | `Tab` | Source Memory selection remains checked when the same `guide` Target frame receives focus | None |
| `10e-same-context-position.png` | `Tab` | The append gap remains reviewable without publishing a self-link | None |
| `10f-same-context-exact-command.png` | `Tab` | The complete same-Context Memory command is focused and valid for review | None |
| `10g-same-context-action-rejected.png` | `Enter` | The exact action, not the picker or live command synchronization, reports that Memory Embed Source and Target must be distinct | None |
| `10h-same-context-read-only-verification.png` | `Escape` | Cancellation closes the rejected path and direct Store verification confirms every Context remains byte-semantically unchanged | None |
| `11-memory-mode.png` | Separate launch, then `Right` | `LINK TYPE` checks `MEMORY`; current `guide` is the initial Source and its direct Memory is immediately visible | None |
| `12-memory-selected.png` | `Tab`, `Up`, `Up`, `Enter`, `Down`, `Enter` | The Source picker moves from current `guide` to peer `archive`, opens its items, and checks the first ordinary Memory; the exact command contains its collision-safe seven-character UID prefix and `--from archive` | None |
| `13-memory-target.png` | `Tab` | Current `guide` remains the reviewed local Target and its existing direct Memory stays visible | None |
| `14-memory-position.png` | `Tab` | The common placement layer owns the checked append gap independently of the Source picker | None |
| `15-memory-exact-command.png` | `Tab` | The blue runnable box shows the short Memory selector, `--from`, Target, and short stable adjacent selector | None |
| `16-memory-success-receipt.png` | `Enter` | The TUI closes and the receipt identifies the Source Memory, Source Context, new Embed UID, Target, and exact gap | One Target save and one Embed checkpoint |
| `17-memory-read-only-verification.png` | `Enter` at the capture-only pause | Actual `mem show --context guide` renders the original Memory followed by `[embedded memory]`, its Source identity, `READ ONLY`, and current Source content | None after Embed |

The pause between `07` and `08` exists only so the success receipt and the
read-only verification are independently reconstructable. It is not part of
the product flow.

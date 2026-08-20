# Grant-backed `mem embed` capture log

This ordered set records the actual color-preserving PTY stream for a granted
Child embedded into an owned local target. It uses a disposable authoring
Profile and authority Profile; no user Profile or research Context is changed.

## Reproduction

- Command: `mem embed`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified by the child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Current/target Context: owned local `guide`
- Source Grant: `advisor`, permissions `READ + EMBED`
- Nested override: `advisor/private`, permissions `QUERY` only
- Renderer: actual cumulative ANSI streams replayed with `pyte`; matching
  `.typescript`, `.txt`, and `.png` files are retained
- Durable scope: temporary stores and Profile registry removed after capture

```bash
env -u NO_COLOR TERM=xterm-256color COLORTERM=truecolor \
  python docs/screenshots/mem-granted-embed-20260814/capture.py
```

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable effect |
| --- | --- | --- | --- |
| `01-entry-granted-source.png` | Launch | Child tree includes `advisor` with `READ + EMBED`; owned `guide` is the initial target. | None |
| `02-query-override-blocked.png` | Tab, Right, Down, Enter | Focus enters the Child tree; nested `advisor/private` is visible for orientation but cannot be selected because its effective Grant is QUERY-only. | None |
| `03-owned-target.png` | Up, Enter, Tab | `advisor` is retained and target focus moves to owned local `guide`; granted rows are not target choices. | None |
| `04-placement-default.png` | Tab | The target's append gap is inspected inside its direct-item order. | None |
| `05-gap-staged.png` | Up, Enter | The gap between the two owned Memories is staged. | None |
| `06-exact-command.png` | Tab | The small blue `COMMAND · RUNNABLE` box contains only exact `mem embed advisor --into guide --before …`; the neighbor is a collision-safe seven-character prefix, and typing remains non-executing until Enter. | None |
| `07-success-receipt.png` | Enter | CLI receipt confirms the reviewed placement. | One local target checkpoint containing a Grant-bound link. |
| `08-read-only-verification.png` | Enter at the first capture pause | Actual recursive `mem ls` expands the typed embedded advisor row and its live Memory under `READ + EMBED`; the query-only note content is absent. | None after Embed. |
| `09-link-receipt.png` | Enter at the capture-only link pause | The raw record reports `granted_context_ref` and `LINK CONTENT CACHED · NO`; current remains `guide`. | None. |

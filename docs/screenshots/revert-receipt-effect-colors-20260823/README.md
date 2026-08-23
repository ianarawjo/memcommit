# Revert receipt typed-effect color capture log

This ordered evidence set records the line-oriented Revert success receipt
after its bounded item-change rows gained the shared semantic effect colors.

## Reproduction frame

- Command:
  `python docs/screenshots/revert-receipt-effect-colors-20260823/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Store: one isolated temporary Store; no personal Profile or Context is read
  or changed
- Profile/current Context: temporary default Profile; current `receipt/colors`
- Fixture: the target checkpoint contains two Memories and one live Memory
  Embed; a later checkpoint removes one Memory and the Embed, edits one Memory,
  and adds one Memory so exact Revert proves ADD, EDIT, REMOVE, Memory-object,
  and relationship colors in one bounded receipt
- PTY: `180` columns × `52` rows, set and printed by every child before launch
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed
- Renderer: the actual color-preserving PTY stream is replayed through `pyte`
  and drawn on a full Menlo terminal canvas; raw `.typescript` and extracted
  `.txt` records remain beside every PNG

## Ordered interaction

| Image | Exact command / input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-before-state.png` | Launch read-only fixture inspector | Current state contains the later edit and addition, while the target Memory is absent; item identities use the shared `[memory UID]` badge order | None |
| `02-success-receipt.png` | `mem revert CHECKPOINT --context receipt/colors` | Exact Revert receipt keeps the aggregate effect summary neutral, then combines effect-colored markers, shared Source identity badges, lavender Memory content, red/green Edit values, and a list-style `receipt/source:MEMORY_UID` live-Embed projection with resolved content and `READ ONLY` | Revert only |
| `03-read-only-verification.png` | Launch read-only verifier | The target's two exact Memories and live Embed are restored and the later Memory is absent | None |

The capture asserts the exact true-color ANSI effect, Memory-object,
relationship, and before/after sequences; the uncolored aggregate summary;
the shared Source identity badge order; the resolved live-Embed locator,
content, and state; the `180×52` PTY; and the final Store state.

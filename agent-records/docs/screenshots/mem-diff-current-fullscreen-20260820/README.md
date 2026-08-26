# Current-scoped full-screen Diff capture log

> Historical evidence for the current-scoped entry and large-change scrolling
> boundary. The checkpoint detail content is refreshed under
> `agent-records/docs/screenshots/revert-revision-result-20260821/`, where Diff and Revert
> share the complete revision-result renderer.

This ordered evidence set records bare `mem diff` opening the current
Context's checkpoint transitions directly in the shared full-screen History
session. It also records an explicit Context operand without switching the
global current Context, plus a 150-change Update fixture that exercises the
full-height Viewer and semantic position reporting.

## Reproduction frame

- Command:
  `python agent-records/docs/screenshots/mem-diff-current-fullscreen-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Store: isolated temporary Store; no personal Profile or Context content is
  read or changed
- Profile/current Context: temporary default Profile; current
  `practice/current`; a separate `practice/unrelated` fixture proves bare Diff
  does not expose the Profile catalog
- Fixture: six retained checkpoints in `practice/current` and two in
  `practice/unrelated`; the large branch contains 50 EDIT, 50 ADD, and 50
  REMOVE operations in one exact Context
- PTY: `180` columns × `52` rows, set before launch and printed by every child
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed,
  prompt-toolkit 24-bit depth; raw streams are checked for ANSI styling
- Renderer: actual color-preserving PTY bytes are replayed through `pyte` and
  drawn on a full Menlo terminal canvas. Raw `.typescript` and plain `.txt`
  evidence is retained beside every PNG.
- Mutation boundary: fixture setup mutates only the temporary Store. Both Diff
  sessions and the final verification are read-only.

## Ordered interaction

| Image | Command/input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-current-entry.png` | Launch bare `mem diff` | `DIFF · practice/current` opens directly in the standard 52-row History session; no Context tree appears | None |
| `02-checkpoint-navigation.png` | `Down` | The next checkpoint and its directional detail are previewed in the full-height Viewer | None |
| `03-viewer-focus.png` | `Enter` | Viewer receives focus while retaining the complete screen and reports its logical change position | None |
| `04-current-close-receipt.png` | `q` | The alternate screen closes; current pointer and complete Store digest are reported unchanged | None |
| `05-explicit-context-entry.png` | Launch `mem diff practice/unrelated` | The exact operand opens directly in the same full-screen layout; current remains `practice/current` | None |
| `06-explicit-close-receipt.png` | `q` | Exact-operand session closes; current pointer and complete Store digest are reported unchanged | None |
| `07-read-only-verification.png` | Launch verifier | Current pointer, both checkpoint counts, and the complete Store digest match the pre-Diff fixture | None |
| `08-large-diff-entry.png` | Launch the 150-change production-renderer fixture | One Item remains below a full-height Viewer; all 150 changes are available | None |
| `09-large-diff-viewer-focus.png` | `Enter` | The full-height Viewer receives focus and reports `CHANGE 1/150` | None |
| `10-large-diff-end-position.png` | `End` | The Viewer exposes the final changes and reports `CHANGE 150/150` | None |
| `11-large-diff-close-receipt.png` | `q` | The synthetic staged session closes without materialization | None |

The capture asserts that every Diff session enters and leaves the terminal
alternate-screen buffer. The Store-backed sessions contain no
`SELECT A CONTEXT`, and the bare session never exposes the unrelated Context
name. The large branch also asserts both endpoint indicators,
`CHANGE 1/150` and `CHANGE 150/150`.

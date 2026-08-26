# Current-scoped Revert and complete revision result capture log

This ordered evidence set records bare Revert entering the command-start
current Context directly and the shared Revert/Diff checkpoint Viewer showing
both a revision's dispositions and its complete resulting direct-item state.

## Reproduction frame

- Command:
  `python agent-records/screenshots/revert-revision-result-20260821/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Stores: two isolated temporary Stores; no active personal Profile or Context
  is read or changed
- Diff routing: the independent Diff Store removes only its temporary active
  Update-session receipt after the production application, so
  `mem diff practice/2` exercises ordinary checkpoint history rather than the
  separate Update-session browser; the applied Context and checkpoint remain
  unchanged
- Profile/current Context: temporary default Profile; current `practice/2`
- Fixture: Init; one three-Memory Add; one Elaborate semantic Add that appends
  `e`, `f`, and `g` through the production `append_semantic_memories` primitive;
  one production Update application that edits `b`, removes `f`, and adds `j`;
  then one later two-Memory Add
- PTY: `180` columns × `52` rows, set and printed by every child before launch
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed,
  prompt-toolkit 24-bit depth; raw streams are checked for foreground and
  background ANSI styles, including a red before-side `-` and green
  after-side `+` in both Revert and Diff
- Renderer: the actual color-preserving PTY stream is replayed through `pyte`
  and drawn on a full Menlo terminal canvas; raw `.typescript` and extracted
  `.txt` records remain beside every PNG
- Mutation boundary: images 01–07 are process-local review; image 08 follows
  the exact Revert Apply in the isolated Revert Store; Diff remains read-only

## Ordered interaction

| Image | Exact command / input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-current-history-entry.png` | Launch bare `mem revert` | `REVERT · practice/2` opens directly with no Context tree; latest revision shows its complete eight-item result | None |
| `02-target-complete-result.png` | `Down` | Update revision selected; one compact stream shows four KEEP rows, adjacent `-`/`+` EDIT rows, one inline REMOVE row, and one ADD row | None |
| `03-revision-viewer-focused.png` | `Shift-Tab` | Viewer owns focus at logical `ITEM 1/7` | None |
| `04-complete-result-end.png` | `End` | Viewer reaches logical `ITEM 7/7`; the EDIT pair remains one item | None |
| `05-exact-revision-staged.png` | `Enter`, `Enter` | Viewer returns to Items, then exact checkpoint is checked and History policy owns focus | None |
| `06-keep-all-policy.png` | `Right` | `KEEP ALL` is the staged newer-checkpoint policy | None |
| `07-exact-apply.png` | `Enter` | Apply repeats the exact checkpoint prefix and keep-all policy | None |
| `08-success-receipt.png` | `Enter` | Revert receipt identifies the restored Update state, two later removed Memories, Undo route, and recovery checkpoint | Revert only |
| `09-read-only-revert-verification.png` | Launch verifier | Current remains `practice/2`; exact six-Memory Update result and keep-all history are verified | None |
| `10-diff-shared-revision-result.png` | Launch `mem diff practice/2`, then `Down` in an independent identical Store | Diff shows the same compact mixed-effect Update stream | None |
| `11-diff-complete-result-end.png` | `Shift-Tab`, `End` | Diff Viewer reaches the same seventh logical item | None |
| `12-diff-read-only-verification.png` | `q` | Diff closes with current pointer and complete Store bytes unchanged | None |

The capture asserts that neither bare command contains `SELECT A CONTEXT`, no
screen contains `RESTORE IMPACT` or `REMOVED BY REVISION`, both use
`REVISION DIFF`, both selected Update revisions contain text-visible
`KEEP`/`EDIT`/`REMOVE`/`ADD` labels and `-`/`+` effect gutters, the alternate
screen is entered and restored, and the terminal stream contains foreground
and background ANSI color styles.

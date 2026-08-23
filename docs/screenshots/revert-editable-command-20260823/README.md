# Revert keep-all and editable-command capture log

This ordered evidence set records Revert's keep-all default, Items-to-command
shortcut, bidirectional synchronization between the visible controls and final
command, durable Apply, and read-only result verification.

## Reproduction frame

- Command: `python docs/screenshots/revert-editable-command-20260823/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Store: isolated temporary Store; no personal Profile or Context is read or
  changed
- Profile/current Context: temporary default Profile; current
`practice/greetings`
- Fixture: Init, Add `bonjour`, then Add `hi`; all three checkpoints are
  ordinary production records
- PTY: `180` columns × `52` rows, set and printed before launch
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed,
  prompt-toolkit 24-bit depth
- Renderer: actual color-preserving PTY bytes replayed through `pyte` and drawn
  on a full Menlo terminal canvas; `.typescript` and `.txt` evidence accompanies
  every PNG
- Mutation boundary: images 01–06 are process-local; image 07 follows Enter on
  the exact reviewed command; image 08 is read-only

## Ordered interaction

| Image | Exact input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-keep-all-default.png` | Launch bare `mem revert` | Current Context history opens with the compact, label-only `KEEP ALL` choice checked and no target staged | None |
| `02-target-preview.png` | `Down` | The `bonjour` checkpoint and its complete result are previewed | None |
| `03-items-enter-direct-command.png` | `Enter` | Exact UID is checked and focus jumps directly to the runnable `PROPOSED COMMAND` with `--keep` | None |
| `04-command-edits-target-and-policy.png` | `Ctrl-U`, then a unique Init UID prefix plus `--context practice/greetings --discard-newer` | The shortened edited command resolves to the full Init checkpoint, moves Items/Viewer there, and checks `DISCARD NEWER` | None |
| `05-history-rewrites-command-keep-all.png` | `Shift-Tab`, `Right` | History owns focus, checks `KEEP ALL`, and rewrites the still-visible command back to `--keep` | None |
| `06-final-reviewed-command.png` | `Enter`, then `Ctrl-U` and the same unique UID prefix with `--keep` | The shortened synchronized command owns final focus and is ready to Apply | None |
| `07-success-receipt.png` | `Enter` | Revert restores Init and prints Undo plus the exact recovery command | Revert only |
| `08-read-only-verification.png` | Launch verifier | Init result is empty and every original active checkpoint remains retained | None |

The capture asserts a truecolor-capable alternate-screen stream, exact
`180×52` dimensions, absence of a redundant `MEANING` line, the default and
revised policy labels, both directions of state synchronization, actual Apply
from a unique UID prefix, the explicit recovery command, and preservation of
all original active checkpoints. Ambiguous prefixes remain invalid.

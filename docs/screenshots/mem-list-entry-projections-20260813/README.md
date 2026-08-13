# `mem list` entry-projection capture log

This ordered capture records the shared Context picker entered through the
direct and recursive `mem list` commands. It demonstrates that `list` keeps the
same navigation grammar as `mem contexts` while opening a different frozen
projection: one exact occurrence root with Memory rows initially visible.

## Reproduction frame

- Command: `python docs/screenshots/mem-list-entry-projections-20260813/capture.py`
- Commands under observation: `mem list task-1/description` and
  `mem list -R task-1/participant/construction-updates`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: the script snapshots the current name before both
  browsers and verifies that neither command changes it
- PTY: `180` columns × `52` rows; the script checks the live `stty size`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the script requires foreground ANSI styling and the
  reverse-video focus style before succeeding.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-direct-entry.png` | Run `mem list task-1/description` | The exact target is the only root and its direct Memory starts visible | None |
| `02-direct-memory-focused.png` | `Down` | Focus moves from the root to its read-only Memory row | None |
| `03-direct-memories-hidden.png` | `m` | The focused Context's Memory layer is hidden without changing the Context | None |
| `04-direct-memories-restored.png` | `m` | The same direct Memory layer is restored | None |
| `05-direct-close-read-only-verification.png` | `q` | The direct browser closes and the current Context is verified unchanged | None |
| `06-recursive-entry.png` | Run `mem list -R task-1/participant/construction-updates` | The exact root, embedded children, and descendant Memory layers start fully expanded | None |
| `07-recursive-row-navigation.png` | `Down` | Focus moves within the expanded occurrence tree using the same picker grammar | None |
| `08-recursive-close-text-verification.png` | `q` | The current Context remains unchanged and noninteractive direct output is printed for verification | None |

No selection receipt, switch continuation, provider turn, or durable mutation
exists in either flow. The shared picker owns navigation only; the `list`
adapter owns the exact-root occurrence snapshot and initial Memory visibility.

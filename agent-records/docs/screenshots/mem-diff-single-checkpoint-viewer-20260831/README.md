# Single-checkpoint Diff read-only Viewer capture log

This ordered 180×52 color-PTY set records the checkpoint-only `mem diff`
flow. The fixture has seven direct coffee Memories; its latest checkpoint edits
four and retains three.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/mem-diff-single-checkpoint-viewer-20260831/capture.py`
- Commands under observation: `mem diff coffee`, then `mem diff coffee --stat`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated temporary home; current Context `coffee`
- PTY: `180` columns × `52` rows, verified by the live child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset,
  prompt-toolkit 24-bit color forced
- Renderer: cumulative actual PTY ANSI bytes replayed through `pyte` and drawn
  at the full 180-column Menlo canvas; matching `.typescript` and `.txt`
  evidence is retained beside each PNG
- Color verification: the capture requires true-color foreground ANSI plus the
  shared red before-text and green after-text RGB values

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-read-only-viewer-entry.png` | Run `mem diff coffee` | One checkpoint revision in the shared `CHECKPOINT REVISION` Viewer; four EDIT pairs are colored and three unchanged Memories are summarized but hidden | None |
| `02-close-and-read-only-verification.png` | `q`; then the child runs `mem diff coffee --stat` | Viewer is closed, the exact checkpoint summary is printed, and all durable store bytes plus the current Context are verified unchanged | None |

There is no Source/target picker, checkpoint picker, response, approval,
success mutation receipt, or Apply branch in this flow. The Viewer is a single
frozen read-only document; `q`, Escape, and Backspace close it.

# Compact natural-language `mem rationale` receipt capture log

This ordered evidence set records Rationale's receipt-only path. The human
result explains the selected content's source context, sentence-Chunk
derivation, Undo/Redo interval, and final Remove as two natural sentences. It
does not expose a raw event chain or open a second read-only Viewer after target
selection.

## Reproduction frame

- Command: `python agent-records/screenshots/mem-rationale-compact-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: capture-local `rationale/origin`
- Fixture: the real public Add and sentence-Chunk commands split `Um...` out of
  the longer minimal-change instruction; Undo, Redo, and Remove reproduce the
  motivating retained Trace before Rationale starts
- PTY: `180` columns × `52` rows, verified inside the child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Provider/cache boundary: the recorded images used the complete version-4
  ruleset; the current deterministic capture harness validates version 5 for
  the same under-limit path, exactly one call, and no legacy inference-cache access
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas with Apple SD Gothic Neo supplying only
  Hangul glyphs; raw `.typescript` and plain `.txt` evidence are retained beside
  each PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-target-entry.png` | Launch bare Rationale | Exact-range target selector for `rationale/origin` with current and historical lineage Memories | None |
| `02-target-focused.png` | `Tab`, three `Down` keys | Historical `Um...` target is focused | None |
| `03-provenance-receipt.png` | `Enter` | Selector closes and the ordinary terminal prints the natural origin-and-lifecycle receipt; no Viewer opens | None |
| `04-read-only-verification.png` | `V`, `Enter` in the capture harness | Child verifies current Context content is unchanged | None |

The capture asserts that raw `CREATED via` output, APPARENT PURPOSE, Saved
Analysis, Context-count, Limits, and `RATIONALE REPORT` Viewer chrome are
absent. Printing the receipt does not mutate Context content or touch a legacy
inference cache.

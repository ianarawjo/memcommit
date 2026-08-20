# Compact `mem rationale` capture log

This ordered evidence set records the shortened Rationale path. The human
report keeps only the selected Memory and its latest Trace-derived reason.
It neither requests nor renders a contextual purpose.
The Korean fixture is the canonical scoped-polishing provenance example shared
with the character-bound cases.

## Reproduction frame

- Command: `python docs/screenshots/mem-rationale-compact-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: capture-local `rationale/korean`
- Fixture: one Korean source replaced by one Korean target through explicit
  trace metadata containing a Korean recorded reason
- PTY: `180` columns × `52` rows, verified inside the child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Provider/cache boundary: the command module exposes no provider connector;
  the capture verifies zero provider calls and no legacy inference-cache access
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas with Apple SD Gothic Neo supplying only
  Hangul glyphs; raw `.typescript` and plain `.txt` evidence are retained beside
  each PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-target-entry.png` | Launch bare Rationale | Exact-range target selector for `rationale/korean` with Korean Memories | None |
| `02-target-focused.png` | `Tab`, `Down` | Edited target Memory is focused | None |
| `03-compact-report.png` | `Enter` | Viewer shows Korean Memory content and its latest Korean recorded reason | None |
| `04-read-only-verification.png` | `q` | Child verifies current Context content is unchanged | None |

The capture asserts that APPARENT PURPOSE, Saved Analysis, Context-count, and
Limits sections are absent. Closing the Viewer does not mutate Context content
or touch a legacy inference cache.

The application chrome remains English; the Memory and retained reason remain
Korean.

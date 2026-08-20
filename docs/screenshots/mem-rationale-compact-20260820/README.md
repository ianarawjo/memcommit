# Compact `mem rationale` capture log

This ordered evidence set records the shortened Rationale path. The human
report keeps only the selected Memory, a Trace-derived provenance summary, and
one contextual WHY paragraph. The human projection omits Context counts and the
`LIMITS` section; detailed scope, warnings, saved analysis, and cited Memory
bodies remain available to JSON consumers but are intentionally absent from
the Viewer.

## Reproduction frame

- Command: `python docs/screenshots/mem-rationale-compact-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: capture-local `practice/source`
- Fixture: one target created and edited, followed by two supporting Memories
- PTY: `180` columns × `52` rows, verified inside the child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Provider boundary: deterministic local provider double using the production
  `explanation + support_ids` schema; its paragraph stays below the dynamic
  NFC-character cap (252 output characters versus a 279-character limit from
  280 unique semantic source characters) and directly states the Memory's
  functional purpose without inventorying the Context
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas; raw `.typescript` and plain `.txt`
  evidence are retained beside each PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-target-entry.png` | Launch bare Rationale | Exact-range target selector for `practice/source` | None |
| `02-target-focused.png` | `Tab`, `Down` | Edited target Memory is focused | None |
| `03-compact-report.png` | `Enter` | Viewer shows Memory, `no reason recorded`, and one WHY paragraph | Replaceable inference cache; no Context mutation |
| `04-read-only-verification.png` | `q` | Child verifies current Context content is unchanged | None |

The capture asserts that Saved Analysis, inference-evidence, Context-count, and
Limits sections are absent. Closing the Viewer does not mutate Context content; the
replaceable inference cache remains the operation's documented derived-data
exception.

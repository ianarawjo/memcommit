# `mem rationale` character-bound edge-case captures

This evidence set runs five actual Rationale paths in isolated stores. Each
report is captured from a `180×52` color PTY and followed by a close receipt
that verifies the Context was unchanged.

## Reproduction frame

- Command: `python docs/screenshots/mem-rationale-character-bounds-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified inside every child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: real cumulative PTY ANSI streams replayed through `pyte` at the
  full `1832×1124` Menlo canvas
- Durable boundary: every scenario uses a temporary isolated store; accepted
  inference may create its replaceable cache, but Context content must remain
  byte-equivalent

## Scenarios and expected boundaries

| Report | Evidence condition | Expected result |
| --- | --- | --- |
| `01-insufficient-report.png` | 2 source characters | limit 1; provider connection count 0; status only |
| `03-minimum-report.png` | 17 source characters | dynamic limit 16; an exact 16-character result is accepted |
| `05-over-limit-report.png` | 33 source characters | dynamic limit 32; a 33-character result is rejected and not cached |
| `07-oversized-context-report.png` | 105 candidates exceed the real 1,000,000-character input bound | nearest 49 candidates retained; absolute limit 480; exact 480-character result accepted |
| `09-long-provenance-report.png` | 13 retained long lineage events | provenance source exceeds 320; projected prose is capped at 320; provider not requested |

Each odd-numbered image is the report state. Its following even-numbered image
is the terminal receipt after `q`, including the observed source/limit or
candidate counts and `STORE UNCHANGED` verification.

The over-limit provider deliberately returns repeated `P` characters. The
capture asserts that this unvalidated text never appears in any rendered report.

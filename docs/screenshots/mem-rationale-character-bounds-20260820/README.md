# `mem rationale` provenance-only boundary captures

This evidence set runs four actual provenance-only Rationale paths with Korean
Memory content in isolated stores. Each report is captured from a `180×52`
color PTY and followed by a close receipt verifying zero provider calls, no
legacy inference-cache access, and unchanged Context content.

The directory name is retained from the earlier character-bound experiment so
existing study links remain valid; its contents now record the provenance-only
replacement contract.

## Reproduction frame

- Command: `python docs/screenshots/mem-rationale-character-bounds-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified inside every child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: real cumulative PTY ANSI streams replayed through `pyte` at the
  full `1832×1124` Menlo canvas with Apple SD Gothic Neo supplying only Hangul
  glyphs
- Durable boundary: every scenario uses a temporary isolated store; Rationale
  performs no provider or cache operation and leaves Context content unchanged

## Scenarios and expected boundaries

| Report | Evidence condition | Expected result |
| --- | --- | --- |
| `01-no-reason-report.png` | selected Memory has no retained operation reason | `PROVENANCE — no reason recorded`; no filler explanation |
| `03-recorded-reason-report.png` | one compact Korean reason is retained in explicit trace metadata | only that latest recorded Korean reason is projected |
| `05-oversized-context-report.png` | 106 Korean Memories exceed 1,000,000 semantic characters | target provenance still opens without contextual analysis, provider, or cache |
| `07-long-reason-report.png` | one coherent retained Korean reason exceeds 160 characters | the latest reason is projected at the 160-character cap, ending at a complete sentence rather than repeated filler |

Each odd-numbered image is the report state. Its following even-numbered image
is the terminal receipt after `q`, including `PROVIDER CALLS 0`,
`CACHE UNTOUCHED`, and `STORE UNCHANGED`.

Every report asserts that APPARENT PURPOSE, a human `LIMITS` section, and a
Context-count row are absent. The application chrome remains English; Korean
here verifies the language of actual Memory and provenance data.

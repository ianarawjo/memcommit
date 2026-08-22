# Audit read-only Review capture log

This ordered set records the large comprehensive Viewer intentionally retained
for a saved Audit. Unlike an answerable Review, it has no Items hub, Responses
frame, selection, draft, To Do, rerun, or Apply action.

## Reproduction frame

- Command: `python docs/screenshots/audit-read-only-review-20260822/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before launch and printed by each child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` unset
- Profile/current Context: not consulted; the Viewer receives one deterministic
  saved Audit snapshot for `study/audit-source`
- Provider: not opened; the three reports and provenance are already saved
- Mutation: none; the close receipt verifies the record digest and zero
  response, Context, and checkpoint writes
- Evidence: each PNG has its color-preserving `.typescript` stream and a
  replayed `.txt` terminal canvas

## Ordered interaction

| Image | Preceding input | Visible state | Following input | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-comprehensive-report-entry.png` | exact saved Audit selected | Audit identity, completed checks, Source, and provenance enter as one report | `Down ×4` | None |
| `02-frozen-source-memory.png` | `Down ×4` | One exact frozen Source Memory focused inside the complete report | `PgDn` | None |
| `03-historical-note-read-only.png` | `PgDn` | A version-1/2 saved response rendered only as a historical note | `Down ×6` | None |
| `04-ambiguity-evidence-not-answer.png` | `Down ×6` | Ambiguity question and possible readings remain report evidence | `Down ×20` | None |
| `05-explicit-read-only-boundary.png` | `Down ×20` | Final non-proof and no-select/no-write/no-rerun/no-Apply boundary | `Q` | None |
| `06-close-no-write-verification.png` | `Q` | Digest unchanged; response/provider/Context/checkpoint writes all zero | process exit | None |
| `07-zero-finding-complete-report.png` | saved zero-finding Audit selected | All three completed checks remain visible with a zero finding count | `Q` | None |

The historical note fixture proves compatibility only. The current Viewer
cannot create or modify that note, and the separate answerable Ambiguity Review
retains its own interaction contract.

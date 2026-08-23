# Audit read-only Review capture log

This ordered set records the comprehensive Viewer retained for a saved Audit
after compacting its document topology. Unlike an answerable Review, it has no
Items hub, Responses frame, selection, draft, To Do, rerun, or Apply action.
Each quality category uses the same semantic color on its section header and
its issue-row token; counts, Source references, and rationale prose stay
neutral.

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
| `01-compact-overview-and-source.png` | exact saved Audit selected | Identity, check counts, Source scope, and every frozen Memory share one overview | `Down` | None |
| `02-duplicate-one-line-evidence.png` | `Down` | The Duplicate relation and exact pair form one line; the retained legacy note is not default report content | `Down` | None |
| `03-ambiguity-one-line-rationale.png` | `Down` | Exact Source, reason, and readings form one natural `WHY` rationale rather than an answer surface | `Down` | None |
| `04-conflict-one-line-evidence.png` | `Down` | The scoped Conflict pair and `WHY` form one evidence line, with no Resolve or Apply action | `Down` | None |
| `05-compact-provenance.png` | `Down` | All three ruleset/provider identities share one provenance section | `Down` | None |
| `06-explicit-read-only-boundary.png` | `Down` | Final non-proof and no-select/no-write/no-rerun/no-Apply boundary | `Q` | None |
| `07-close-no-write-verification.png` | `Q` | Digest unchanged; response/provider/Context/checkpoint writes all zero | process exit | None |
| `08-zero-finding-complete-report.png` | saved zero-finding Audit selected | All three completed zero-finding checks remain explicit | `Q` | None |

The historical note fixture proves decode and no-write compatibility only. The
compact default Viewer neither displays nor modifies that note, and the
separate answerable Ambiguity Review retains its own interaction contract.

# Audit read-only Review capture log

This ordered set records the comprehensive Viewer retained for a saved Audit
after compacting its document topology. Unlike an answerable Review, it has no
Items hub, Responses frame, selection, draft, To Do, rerun, or Apply action.
Each quality category uses the same semantic color on its check header and its
result-row token; counts, Source references, and rationale prose stay neutral.
The check header and every individual result are separate semantic scroll
stops, so a category with many results never moves as one large block.
On a focused result, its leading `=`, `≈`, `?`, or `!` marker turns focus blue
while the adjacent category label retains its Redundancy, Ambiguity, or Conflict
semantic color and becomes bold. Unfocused finding labels are non-bold, while
the category check headers remain bold to preserve their higher-level visual
hierarchy.

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
| `02-duplicate-check-header.png` | `Down` | Redundancy groups and proposed absorptions form their own category header stop | `Down` | None |
| `03-duplicate-one-line-evidence.png` | `Down` | The blue `≈` marker identifies the independently focused finding while `REDUNDANT` retains its semantic color; the retained legacy note is not default report content | `Down` | None |
| `04-ambiguity-check-header.png` | `Down` | The bold Ambiguity header is focused while subordinate result labels remain non-bold | `Down` | None |
| `05-first-ambiguity-finding.png` | `Down` | The first blue `?` and bold yellow `UNDERSPECIFIED` identify the focused result; Source, reason, ordinary reading, and question remain one read-only paragraph | `Down` | None |
| `06-second-ambiguity-finding.png` | `Down` | The blue `?` moves to the second finding in the same category with its independent viewport anchor | `Down` | None |
| `07-conflict-check-header.png` | `Down` | The bold Conflict header is focused while its subordinate red `CONFLICT` remains non-bold | `Down` | None |
| `08-conflict-one-line-evidence.png` | `Down` | The blue `!` and bold red `CONFLICT` identify the focused result; its pair, reason, and question remain one unit with no scope taxonomy, Resolve, or Apply action | `Down` | None |
| `09-compact-provenance.png` | `Down` | All three ruleset/provider identities share one provenance section | `Down` | None |
| `10-explicit-read-only-boundary.png` | `Down` | Final non-proof and no-select/no-write/no-rerun/no-Apply boundary | `Q` | None |
| `11-close-no-write-verification.png` | `Q` | Digest unchanged; response/provider/Context/checkpoint writes all zero | process exit | None |
| `12-zero-finding-complete-report.png` | saved zero-finding Audit selected | All three completed zero-finding checks remain explicit | `Q` | None |

The historical note fixture proves decode and no-write compatibility only. The
compact default Viewer neither displays nor modifies that note, and the
separate answerable Ambiguity Review retains its own interaction contract.

# Initial semantic progress and reviewed replacement capture log

This ordered set renders the actual color-preserving PTY stream from the
shared production `run_command_wait` boundary. It verifies the cross-operation
presentation policy directly: first analysis stays on one transient progress
line, while a replacement turn submitted from a complete review retains that
previous report in the full-screen read-only wait.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/inline-semantic-analysis-20260821/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before launch and verified by the child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile/current Context: none; the harness exercises the operation-neutral
  presentation boundary with deterministic synthetic blocking work
- Provider payload: none; no provider, Store, Profile, Context, or session is
  opened or changed
- Renderer: cumulative ANSI replay with `pyte`, rendered at `1980×1092` using
  DejaVu Sans Mono; `.typescript` and `.txt` evidence accompanies every PNG
- Assertions: no initial segment may contain the alternate-screen entry or
  `REPORT · BUILDING`; the review replacement must enter the alternate screen;
  the combined raw stream must contain ANSI controls and foreground color

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-compare-inline-analysis.png` | Enter at the Compare harness gate | `MEM COMPARE · 2/2 · ANALYZING RELATIONS` on one transient line | None |
| `02-meld-inline-analysis.png` | Enter after Compare completes | `MEM MELD · 2/2 · ANALYZING MELD TURN` on the same line contract | None |
| `03-update-inline-analysis.png` | Enter after Meld completes | `MEM UPDATE · 2/2 · PLANNING MEMORY CHANGES`; no report topology | None |
| `04-forget-inline-analysis.png` | Enter after Update completes | Whole-frame Forget stage on one line; no pending decision report | None |
| `05-sever-inline-analysis.png` | Enter after Forget completes | Final Source × Criteria analysis stage on one line | None |
| `06-audit-inline-analysis.png` | Enter after Sever completes | Audit advances to `FINDING CONFLICTS` without a cumulative full-screen box | None |
| `07-prior-review-replacement.png` | Enter at the review-replacement gate | Previous complete Update report plus visibly unincorporated submitted revision | None |
| `08-submitted-review-inputs.png` | `i` | Exact Source, Target, and submitted comment in the review-only wait | None |
| `09-review-replacement-result.png` | `i`, then deterministic work completes | Full-screen wait closes and the exact replacement result returns | None |
| `10-read-only-verification.png` | Enter at the capture-only verification gate | All six initial operations report one-line presentation; review replacement retained the prior report | None |

The gates and final verification text belong only to the deterministic capture
harness. The progress lines, alternate-screen behavior, prior-review pane,
input destination, footer, styles, and result handoff come from the production
shared command-wait implementation.

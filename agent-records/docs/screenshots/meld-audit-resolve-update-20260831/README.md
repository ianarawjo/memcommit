# Meld Audit→Resolve→Update terminal capture

Captured 2026-08-31 from the repository checkout with the actual symmetric Meld
command adapter. The path freezes both Sources into one lossless candidate,
runs the complete Audit application, uses the Resolve-owned decision Viewer,
plans one ordinary whole-candidate Update, materializes it detached, runs a
complete post-image Audit plus exhaustive Source-claim coverage, and only then
applies the exact target effects. Semantic responses are deterministic in
`capture.py`; the provider gates pause otherwise transient real command stages
and are not product UI.

## Environment

- Command: `mem meld capture/meld/incoming capture/meld/baseline --to capture/meld/result`
- PTY: `180` columns × `52` rows, verified by the child process
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, prompt-toolkit 24-bit
  depth, and `NO_COLOR` removed
- Profile: isolated temporary Store
- Current Context: `capture/meld/baseline`
- Result Context: absent at command start; initialized empty with the reviewed
  candidate session, then populated only at verified Apply
- Every `.typescript` is the cumulative color-preserving PTY stream at that
  step; every `.txt` is its 180×52 terminal projection; every `.png` renders
  the same canvas. The PNG renderer adds the beam at the PTY cursor coordinate
  when the real stream requests the blinking-beam cursor.

## Ordered interaction log

| Image | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-first-conflict.png` | launch command | First of two candidate Audit conflicts in the Resolve-owned Viewer under the `MELD` label | immutable Audit and candidate session only |
| `02-confirmed-first-next-row.png` | `Enter`, `Down ×4` | First recommended understanding selected; NEXT is focused | none beyond saved review evidence |
| `03-next-second-conflict.png` | `Enter` on NEXT | Second conflict at `< 2/2 >`; first decision retained | none |
| `04-intent-inline-field.png` | `Down` | Choice 2 targets the inline intent field with a blinking beam cursor | none |
| `05-finalize-two-decisions.png` | type exact intent, `Enter`, `Down ×4` | Confirm plus intent are frozen; Finalize 2/2 is ready | none |
| `06-whole-candidate-update.png` | `Enter` on Finalize | Ordinary Update is planning once against the complete detached candidate | none |
| `07-post-image-audit.png` | `u`, `Enter` | The detached post-image is undergoing the full Audit before target publication | none |
| `08-new-conflict-next-round.png` | `c`, `Enter` | A post-image conflict opens a new Resolve round; the initialized target remains empty | next candidate review only |
| `09-force-selected.png` | `Down ×2`, `Enter` | LEAVE UNRESOLVED is the explicit selected disposition | none beyond review evidence |
| `10-second-update.png` | `Down`, `Enter` on Finalize | The exact second-round input is projected through one complete-candidate Update | none |
| `11-force-post-image-audit.png` | `u`, `Enter` | The unchanged forced issue is independently re-observed in post-image Audit | none |
| `12-applied-unresolved-receipt.png` | `c`, `Enter` | Verified target applied with one unresolved Audit key recorded in the receipt | target Context, checkpoint, applied session |
| `13-read-only-verification.png` | `v`, `Enter` | Persisted result, finalized decisions, unresolved key count, and applied session reloaded read-only; Sources remain unchanged | none after receipt |
| `14-no-issue-direct-update.png` | fresh command whose complete initial Audit has zero items | No decision Viewer opens; ordinary whole-candidate Update starts directly | immutable Audit and candidate session only |
| `15-no-issue-post-image-audit.png` | `u`, `Enter` | The detached clean candidate is still fully re-Audited before Apply | none |
| `16-no-issue-applied-receipt.png` | `c`, `Enter` | Direct applied receipt with unresolved count 0 | target Context, checkpoint, applied session |
| `17-no-issue-read-only-verification.png` | `v`, `Enter` | Clean persisted result and empty finalized-decision list reloaded read-only | none after receipt |

The script verifies both true-color ANSI output and the blinking-beam cursor
request. It deletes only this directory's numbered generated artifacts when
refreshing the set.

# Resolve decision-to-Update terminal capture

Captured 2026-08-31 from the repository checkout with the actual Resolve
command adapter, durable Audit repository, all three Audit finders, Resolve
direction turn, Resolve TUI, ordinary Update planner/decoder, detached Update
application, complete post-image Audit, Store Apply boundary, receipt renderer,
and read-only Store verification. Semantic responses are supplied by the
deterministic provider in `capture.py`; `UPDATE PROVIDER GATE` and `POST-IMAGE
AUDIT GATE` pause otherwise transient real command stages for capture and are
not product UI.

## Environment

- Command: `mem resolve capture/resolve`
- PTY: `180` columns × `52` rows, verified by the child process
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, prompt-toolkit 24-bit
  depth, and `NO_COLOR` removed
- Profile: isolated temporary Store
- Current Context: `capture/resolve`
- Initial Memories:
  - `memory-general`: `Named greetings always end with a period.`
  - `memory-exception`: `Named greetings may omit punctuation.`
  - `memory-house-rule`: `All greetings follow the house punctuation rule.`
- Every `.typescript` is the cumulative color-preserving PTY stream at that
  step; every `.txt` is its 180×52 terminal projection; every `.png` renders
  that same projected canvas.

## Ordered interaction log

| Image | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-first-conflict.png` | launch command | First of two Audit items, three explicit decisions, a non-focusable inline intent field, navigation row, Finalize 0/2 | saved read-only Audit only |
| `02-confirmed-first-next-row.png` | `Enter`, `Down ×4` | First direction accepted; selectable NEXT row focused | none beyond the Audit |
| `03-next-second-conflict.png` | `Enter` on NEXT | Second Audit item at `< 2/2 >`; first decision retained | none beyond the Audit |
| `04-intent-selected-inline-field.png` | `Down`, `Enter` | Choice 2 selected and its inline YOUR INTENT editor active; the blank intent is still not ready | none beyond the Audit |
| `05-intent-entered-finalize-ready.png` | type `The exception applies only to named greetings.`, `Enter`, `Down ×4` | Exact intent frozen at choice 2; one Down would move to choice 3, while Finalize 2/2 READY is now focused | none beyond the Audit |
| `06-update-planning.png` | `Enter` on Finalize | Existing Update planner is processing one process-local Source against the complete Target | none |
| `07-post-image-audit-check.png` | `u`, `Enter` | Exact UpdatePlan has been applied detached; all post-image Audit sections are running | none |
| `08-applied-receipt.png` | `c`, `Enter` | Two UPDATE effects, zero Audit issues, one Resolve checkpoint, Review and undo routes | checkpoint plus two Memory edits |
| `09-read-only-verification.png` | `v`, `Enter` | Persisted Context and checkpoint inputs loaded read-only; CONFIRM and exact INTENT retained; unresolved count 0 | none after receipt |
| `10-force-selected.png` | fresh unresolved branch; `Down ×2`, `Enter` | LEAVE UNRESOLVED selected; Finalize 1/1 READY | saved read-only Audit only |
| `11-force-post-image-check.png` | `Down`, `Enter` on Finalize | Empty UpdatePlan bypassed Update provider; the complete unchanged post-image Audit is running | none beyond the Audit |
| `12-force-unresolved-receipt.png` | `c`, `Enter` | No Memory changes, one verified Audit issue permitted by the exact unresolved decision, unresolved count 1 | Resolve checkpoint only |
| `13-force-read-only-verification.png` | `v`, `Enter` | Original Memories unchanged; exact FORCE input and unresolved Issue retained in checkpoint | none after receipt |

The capture script verifies that the accumulated PTY streams contain true-color
ANSI sequences. It deletes only this directory's numbered generated artifacts
before refreshing them.

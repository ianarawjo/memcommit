# Direct Update final-review captures

These ordered captures record the 2026-08-30 direct local `mem update` path
after direct invocation gained one explicit pre-Apply review. The run uses a
real color-capable PTY at 180 columns × 52 rows with `TERM=xterm-256color`,
`COLORTERM=truecolor`, `NO_COLOR` removed, and the local capture profile. Raw
`.typescript`, text, and PNG projections are retained together.

## Ordered interaction log

1. `01-provider-pending.png`
   - Command: `mem update --from capture/update-review/new-guidance --to capture/update-review/campus-guide`
   - PTY: 180×52; Current Context: `capture/update-review/new-guidance`
   - Preceding input: none.
   - Visible state: the selected Source and Target are printed while the
     provider plans one exact edit.
   - Durable mutation: none.
2. `02-review-entry.png`
   - Preceding input: none; provider planning completed.
   - Visible state: the direct Update report shows the exact before/after
     change and the `APPLY CONFIRMATION` action before the local Target changes.
   - Durable mutation: none; the staged compatibility record exists.
3. `03-exact-apply-confirmation.png`
   - Preceding input: `A` from the report.
   - Visible state: `APPLY CONFIRMATION` shows the exact Update action before
     acceptance.
   - Durable mutation: none.
4. `04-success-receipt.png`
   - Preceding input: `Down`, `Enter` on the exact Apply action.
   - Visible state: compact `UPDATE APPLIED` receipt with one EDIT, checkpoint,
     Review handoff, and Undo recovery.
   - Durable mutation: the local Target Memory was updated.
5. `05-read-only-verification.png`
   - Preceding input: `V` at the capture-only verification gate.
   - Visible state: applied session, exactly one provider call, one Target
     Memory, one checkpoint, and the updated content.
   - Durable mutation: none; this step only reloads retained state.

Run `python agent-records/docs/screenshots/update-direct-final-review-20260830/capture.py`
from the repository root to refresh the complete set.

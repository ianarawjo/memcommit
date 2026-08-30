# Direct Update report-Apply captures

These ordered captures record the 2026-08-30 direct local `mem update` path
after Update became one exact report with one inline `APPLY` action. Esc
cancels the invocation without creating a terminal receipt. The directory
retains its original path so existing evidence links remain stable. The
refreshed flow has no proposal-revision turn and no separate Apply-confirmation
screen.

Both runs use a real color-capable PTY at 180 columns × 52 rows with
`TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed, and an
isolated local capture profile. Raw `.typescript`, text, and PNG projections
are retained together.

## Ordered interaction log

1. `01-provider-pending.png`
   - Command: `mem update --from capture/update-review/new-guidance --to capture/update-review/campus-guide`
   - PTY: 180×52; Current Context: `capture/update-review/new-guidance`
   - Preceding input: none.
   - Visible state: the selected Source and Target while one exact proposal is
     planned.
   - Durable mutation: none.
2. `02-report-apply.png`
   - Preceding input: provider planning completed.
   - Visible state: the exact report, its single `APPLY` action, and the
     `Press Esc to cancel` guidance.
   - Durable mutation: none; the staged record exists.
3. `03-apply-focused-before-cancel.png`
   - Preceding input: `Shift-Tab`.
   - Visible state: the `APPLY` frame and its only action own focus; Esc remains
     the visible cancellation path.
   - Durable mutation: none.
4. `04-cancelled.png`
   - Preceding input: `Esc` from the focused `APPLY` frame.
   - Visible state: `UPDATE CANCELLED` states that the Target is unchanged and
     the staged proposal remains resumable.
   - Durable mutation: no Target change, Context checkpoint, or terminal receipt.
5. `05-cancel-verification.png`
   - Preceding input: `V` at the capture-only verification gate.
   - Visible state: staged session, one planning call, unchanged Target
     content, and zero checkpoints.
   - Durable mutation: none; this step only reloads retained state.
6. `06-apply-selected.png`
   - Command: the same command against a fresh isolated store.
   - Preceding input: provider planning completed, then `Shift-Tab`.
   - Visible state: the report remains visible while `APPLY` owns focus.
   - Durable mutation: none; the staged record exists.
7. `07-apply-receipt.png`
   - Preceding input: `Enter` on `APPLY`.
   - Visible state: compact `UPDATE APPLIED` receipt with one EDIT, checkpoint,
     Review handoff, and Undo recovery.
   - Durable mutation: the local Target Memory was updated.
8. `08-apply-verification.png`
   - Preceding input: `V` at the capture-only verification gate.
   - Visible state: applied session, one planning call, updated Target content,
     and one checkpoint.
   - Durable mutation: none; this step only reloads retained state.

Run `python agent-records/docs/screenshots/update-direct-final-review-20260830/capture.py`
from the repository root to refresh the complete set.

# Decision-free final approval capture

These snapshots record the shared Resolution Session rule introduced for an
applicable proposal with no unanswered `REQUIRED` decisions: the owning
workbench starts at final review, but explicit Apply remains mandatory and Back
returns to the complete report. Update supplies `NONE` obligations; Atomize
supplies `OPTIONAL` findings.

## Environment

- Capture date: 2026-08-13
- Command: `python docs/screenshots/decision-free-final-approval-20260813/capture_decision_free_final.py`
- PTY: real `pexpect` PTY, verified with `stty size` as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` removed
- Evidence: every PNG is rendered from its matching color-preserving
  `.typescript`; a `.txt` visible-canvas projection is stored beside it
- Store: an isolated temporary `MemoryStore`; no configured Profile or global
  current Context was read or changed
- Provider: deterministic local capture providers; no network/provider
  connection

## Ordered interaction log

1. `01-update-direct-final-approval.png`
   - Child command: `capture_decision_free_final.py --child update STORE`
   - Preceding input: none
   - Visible state: Update opens at `REVIEW AND APPLY`; `Apply Update` is visible
     but has not been confirmed
   - Durable mutation: Source, Target, and a staged Update receipt were created
     in the isolated store; Target Memory unchanged

2. `02-update-back-to-complete-report.png`
   - Preceding key: `Escape`
   - Visible state: complete staged Update report with exact located Impact and
     the `REVIEW AND APPLY` handoff
   - Durable mutation: none; Target Memory unchanged and receipt remains staged

3. `03-update-application-receipt.png`
   - Preceding keys: `A`, `Down`, `Enter`
   - Visible state: successful Update application receipt after the exact final
     action was selected
   - Durable mutation: the target Memory was edited, an Update checkpoint was
     written, and the staged receipt became applied

4. `04-update-read-only-verification.png`
   - Child command: `capture_decision_free_final.py --child verify-update STORE`
   - Preceding input: none
   - Visible state: applied receipt status, updated Memory content, and one
     Update checkpoint
   - Durable mutation: none (`MemoryStore(create=False)`)

5. `05-atomize-direct-final-approval.png`
   - Child command: `capture_decision_free_final.py --child atomize STORE`
   - Preceding input: none
   - Visible state: Atomize opens at `REVIEW AND APPLY`; two unanswered optional
     findings are disclosed and `Apply Atomize as is` awaits confirmation
   - Durable mutation: an Atomize analysis and workbench were saved in the
     isolated store; Context Memory unchanged

6. `06-atomize-back-to-optional-report.png`
   - Preceding key: `Escape`
   - Visible state: complete Atomize report, both optional findings, Items, and
     the final-review handoff remain inspectable
   - Durable mutation: none; Context Memory unchanged

7. `07-atomize-application-receipt.png`
   - Preceding keys: `A`, `Down`, `Enter`
   - Visible state: successful `APPLIED AS IS` receipt with the preserved Memory
     and unresolved-at-apply count
   - Durable mutation: one Atomize checkpoint and terminal workbench application
     receipt were written; the uncertain source Memory was deliberately
     preserved

8. `08-atomize-read-only-verification.png`
   - Child command: `capture_decision_free_final.py --child verify-atomize STORE`
   - Preceding input: none
   - Visible state: unchanged Memory, exact application Output/checkpoint
     identity, and one Atomize checkpoint
   - Durable mutation: none (`MemoryStore(create=False)`)

The capture script fails if either flow skips explicit final confirmation, if
the read-only verification does not find its operation checkpoint, or if the
raw initial PTY stream does not contain ANSI true-color output.

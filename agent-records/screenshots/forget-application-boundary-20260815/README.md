# Forget application-boundary capture

This ordered replay records the complete `mem forget` APPLY-01 boundary. A
decision-free local change applies through one CAS-checked checkpoint and is
recoverable as one Undo/Redo unit. A change to a granted Source retains final
review. An all-KEEP granted result publishes no Context mutation and therefore
needs neither authority review nor an artificial checkpoint.

## Environment

- Capture date: 2026-08-15
- Command: `python agent-records/screenshots/forget-application-boundary-20260815/capture.py`
- PTY: real `pexpect` PTY, set and verified as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` removed
- Evidence: each PNG is rendered from its matching color-preserving
  `.typescript`; the matching `.txt` is the final visible-canvas projection
- Store: isolated temporary `MemoryStore` roots; no real Profile or current
  Context was read or changed
- Provider: deterministic local complete-coverage Forget providers; no network
  connection

## Ordered interaction log

1. `01-local-result-pending.png`
   - Child command: `capture.py --child local STORE`
   - Preceding input: none
   - Visible state: report skeleton while one whole-frame provider turn runs
   - Durable mutation: none

2. `02-local-confirmed-input.png`
   - Preceding key: `i`
   - Visible state: frozen direct Source, Memory count, instruction, and
     unchanged Source status while the same provider turn continues
   - Durable mutation: none

3. `03-local-auto-application-receipt.png`
   - Preceding input: none; provider returns one DELETE disposition
   - Visible state: local auto-application receipt with checkpoint and
     `mem undo` recovery
   - Durable mutation: one Memory removed and one `forget` checkpoint written

4. `04-read-only-applied-verification.png`
   - Child command: `capture.py --child verify STORE`
   - Visible state: zero direct Memories and exactly one Forget checkpoint
   - Durable mutation: none (`MemoryStore(create=False)`)

5. `05-operation-unit-undo.png`
   - Child command: `capture.py --child undo STORE`
   - Visible state: canonical Forget Undo receipt and restored Source Memory
   - Durable mutation: the complete Forget command unit is undone

6. `06-operation-unit-redo.png`
   - Child command: `capture.py --child redo STORE`
   - Visible state: canonical Forget Redo receipt and zero direct Memories
   - Durable mutation: the same Forget command unit is redone

7. `07-granted-change-final-review.png`
   - Child command: `capture.py --child granted-review STORE`
   - Preceding input: none; the deterministic provider proposes DELETE
   - Visible state: exact final Apply action remains required for an authority
     mutation
   - Durable mutation: fixture creation only; Source unchanged

8. `08-granted-change-complete-report.png`
   - Preceding key: `Escape`
   - Visible state: complete report and exact proposed Source impact
   - Durable mutation: none

9. `09-granted-change-cancelled.png`
   - Preceding key: `q`
   - Visible state: cancellation receipt and one surviving authority Source
     Memory
   - Durable mutation: none after fixture creation

10. `10-granted-all-keep-noop.png`
    - Child command: `capture.py --child granted-noop STORE`
    - Provider result: one explicit KEEP disposition
    - Visible state: accepted no-change receipt, Context unchanged, no
      checkpoint, and mutation boundary `NONE`
    - Durable mutation: none after fixture creation

11. `11-stale-review-rejected.png`
    - Child command: `capture.py --child stale STORE`
    - Precondition: a second writer adds one Memory after Source load but before
      application
    - Visible state: digest mismatch error, preserved two-Memory current Source,
      and zero Forget checkpoints
    - Durable mutation: only the intentionally concurrent Add; no partial Forget

The capture script fails if local Forget opens a final review instead of
auto-applying, if Undo/Redo does not restore the complete batch, if a granted
change skips final review, if cancellation mutates the Source, if a granted
all-KEEP result creates a checkpoint, if stale CAS publishes any Forget effect,
or if the final-review PTY stream lacks ANSI true-color styles.

# Ownership-aware auto-application capture

These committed snapshots use Update to record the ownership-aware application
boundary. A complete proposal with no unanswered `REQUIRED` decision applies
without opening a review window when it writes only local state and an Undo
checkpoint exists. The same proposal still opens exact final review when it
would mutate granted authority state. A zero-operation proposal has no Context
mutation boundary and therefore needs neither authority review nor an Undo
checkpoint.

## Environment

- Original capture date: 2026-08-13; full set refreshed and zero-change Update
  evidence added on 2026-08-15
- Command: `python agent-records/screenshots/ownership-aware-auto-application-20260813/capture_ownership_aware_auto.py`
- PTY: real `pexpect` PTY, verified with `stty size` as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` removed
- Evidence: every PNG is rendered from its matching color-preserving
  `.typescript`; a `.txt` visible-canvas projection is stored beside it
- Store: an isolated temporary `MemoryStore`; no configured Profile or global
  current Context was read or changed
- Provider: deterministic local capture providers; no network/provider
  connection

This set verifies Update only. Other operations must retain their own focused
rollout evidence rather than inheriting Update's materialization semantics.

## Ordered interaction log

1. `01-update-local-auto-application.png`
   - Child command: `capture_ownership_aware_auto.py --child update STORE`
   - Preceding input: none
   - Visible state: successful Update receipt; no review application was opened
   - Durable mutation: local Target Memory edited, Update checkpoint written,
     staged receipt marked applied

2. `02-update-read-only-verification.png`
   - Child command: `capture_ownership_aware_auto.py --child verify-update STORE`
   - Preceding input: none
   - Visible state: applied receipt, new Memory content, one Update checkpoint
   - Durable mutation: none (`MemoryStore(create=False)`)

3. `03-update-undo-recovery.png`
   - Child command: `capture_ownership_aware_auto.py --child undo-update STORE`
   - Preceding input: none; this is the exact recovery action named by the
     auto-application receipt
   - Visible state: command-unit Undo receipt, `UNDONE` Update artifact, original
     Target Memory content
   - Durable mutation: the local Update command was undone and its recovery
     checkpoint was recorded

4. `04-granted-update-final-review.png`
   - Child command: `capture_ownership_aware_auto.py --child granted-update STORE`
   - Preceding input: none
   - Visible state: exact final `REVIEW AND APPLY` remains mandatory because the
     proposal targets granted authority state
   - Durable mutation: local capture fixtures and staged receipt only; authority
     Target Memory unchanged

5. `05-granted-update-back-to-report.png`
   - Preceding key: `Escape`
   - Visible state: complete staged Update report and exact Impact
   - Durable mutation: none; authority Target Memory unchanged

6. `06-granted-update-cancelled-unchanged.png`
   - Preceding key: `q`
   - Visible state: staged receipt retained and authority Target verified
     unchanged
   - Durable mutation: none after fixture/session setup

7. `09-granted-update-noop-no-mutation.png`
   - Child command: `capture_ownership_aware_auto.py --child granted-update-noop STORE`
   - Preceding input: none
   - Visible state: the exact zero-operation proposal returns its completion
     action without opening authority review
   - Durable mutation: fixture and staged receipt only; Target unchanged and no
     Context checkpoint because the classified mutation boundary is `NONE`

The capture script fails if a decision-free local Update opens review instead
of returning its exact Accept action, if a granted Target with changes skips
final review, if closing granted review mutates the Target, if Update Undo does
not restore the original Memory, if a granted zero-operation proposal opens
review, or if the raw PTY stream lacks ANSI true-color output.

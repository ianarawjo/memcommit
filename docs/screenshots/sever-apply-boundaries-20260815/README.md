# Sever APPLY-01 boundary capture

This ordered replay records the local Sever path after tightening freshness,
compensation, and interrupted-Apply recovery. It also fixes the intended
all-KEEP meaning: Source is unchanged, but the reviewed Result is still a real
new Context with one Sever checkpoint.

## Environment

- Capture date: 2026-08-15
- Command: `python docs/screenshots/sever-apply-boundaries-20260815/capture.py`
- PTY: real `pexpect` PTY, explicitly set and verified as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed
- Store: isolated temporary `MemoryStore` roots; no user Context was read or
  changed
- Provider: deterministic local complete-coverage Sever provider; no network
  connection
- Provenance: every PNG is rendered from its color-preserving `.typescript`;
  the matching `.txt` is the final visible-canvas projection

## Ordered interaction log

1. `01-analysis-pending.png`
   - Command: `mem sever --source sever/source --criteria sever/criteria
     --save-as sever/result --accept`
   - Preceding input: none
   - Visible state: report skeleton and explicit pending status during the one
     complete Source × Criteria provider turn
   - Durable mutation: fixture creation only; no Result

2. `02-all-keep-application-receipt.png`
   - Provider result: one `KEEP_AS_WRITTEN` disposition
   - Visible state: `APPLIED · SOURCE UNCHANGED`, local output name, exact
     candidate result, and `mem undo` recovery
   - Durable mutation: one new Result Context and one Sever checkpoint; Source
     remains one Memory

3. `03-read-only-result-verification.png`
   - Child mode: open the saved session and Result using `create=False`
   - Visible state: one Result Memory and exactly one checkpoint
   - Durable mutation: none

4. `04-operation-undo.png`
   - Operation: exact command-unit Undo
   - Visible state: canonical Sever Undo receipt and absent Result
   - Durable mutation: Result Context moved into the private recovery archive;
     saved session returned to REVIEWING

5. `05-operation-redo.png`
   - Operation: exact command-unit Redo
   - Visible state: canonical Sever Redo receipt and restored Result
   - Durable mutation: same Result and APPLIED receipt restored

6. `06-session-failure-compensated.png`
   - Precondition: injected synchronous failure at APPLIED session receipt CAS
     after Result creation
   - Visible state: failure, absent Result, and REVIEWING session
   - Durable mutation: none after compensation; the exact new Context and sole
     checkpoint were removed without a lifecycle deletion event

7. `07-interrupted-apply-recovered.png`
   - Precondition: exact Result/checkpoint created while the session remains
     REVIEWING, reproducing interruption in the two-file gap
   - Visible state: APPLIED receipt, `CREATED THIS TURN False`, and the same
     Result UID
   - Durable mutation: missing session receipt recovered; no duplicate Result
     was created

The script fails if the PTY is not 180×52 and color-capable, all-KEEP is
treated as a no-op, Source changes, the Result/checkpoint is missing, Undo/Redo
does not restore the operation unit, synchronous receipt failure leaves a
partial Result, or interrupted Apply creates a second identity.

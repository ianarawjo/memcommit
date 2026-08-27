# Atomize in-place APPLY-01 boundary capture

This ordered replay records the local Atomize in-place Apply path after moving
materialization and terminal receipt persistence behind typed application and
runtime ports. It was replayed again after the saved-workbench screen moved to
`memcommit.adapters.interfaces.tui.operations.atomize`; the command compatibility path
is not used by the recorder. The semantic assessment, explicit `--save`
command boundary, ordinary success receipt, and visible terminal grammar remain
unchanged.

## Environment

- Capture date: 2026-08-15
- Command: `python agent-records/docs/screenshots/atomize-apply-boundaries-20260815/capture.py`
- PTY: real `pexpect` PTY, explicitly set and verified as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed
- Store: isolated temporary `MemoryStore` roots; no user Context was read or
  changed
- Provider: deterministic local one-UNCERTAIN Atomize provider; no network
  connection
- Provenance: every PNG is rendered from its color-preserving `.typescript`;
  the matching `.txt` is the final visible-canvas projection

## Ordered interaction log

1. `01-reviewed-analysis.png`
   - Context: `atomize/apply-boundary`
   - Preceding input: none
   - Visible state: complete one-UNCERTAIN analysis in the shared Resolution
     Session
   - Durable mutation: fixture plus saved analysis/workbench; no Context
     checkpoint

2. `02-application-receipt.png`
   - Command: `mem atomize --context atomize/apply-boundary --save`
   - Precondition: the exact saved workbench reviewed in step 1; the explicit
     `--save` invocation is this non-interactive adapter's Apply boundary
   - Visible state: ordinary in-place success receipt, one deliberate
     no-content-change checkpoint, and terminal receipt verification
   - Durable mutation: one Atomize Context checkpoint and one terminal
     workbench receipt

3. `03-read-only-verification.png`
   - Child mode: reopen the saved analysis/workbench and Context with
     `create=False`
   - Visible state: the preserved Memory, APPLIED workbench, exactly one
     checkpoint, and matching receipt
   - Durable mutation: none

4. `04-receipt-failure-compensated.png`
   - Precondition: injected synchronous failure before terminal receipt CAS
     can commit
   - Visible state: Atomize error plus zero checkpoints and no terminal receipt
   - Durable mutation: none after exact compensation; Context bytes and the
     REVIEWING workbench remain the accepted pre-Apply state

5. `05-late-success-reread.png`
   - Precondition: terminal receipt commits atomically and the write then
     reports an injected I/O failure
   - Visible state: normal success, one checkpoint, and a durable receipt
   - Durable mutation: one checkpoint and one terminal receipt; the application
     layer re-read the committed record instead of rolling it back

6. `06-interrupted-checkpoint-recovered.png`
   - Precondition: exact Context checkpoint exists while its workbench remains
     REVIEWING, reproducing interruption in the two-record gap
   - Visible state: normal receipt with explicit recovered-checkpoint notice
     and the same checkpoint identity
   - Durable mutation: missing receipt only; no duplicate checkpoint

7. `07-recovery-read-only-verification.png`
   - Child mode: reopen the recovered records with `create=False`
   - Visible state: one preserved Memory, exactly one checkpoint, and terminal
     receipt
   - Durable mutation: none

8. `08-workbench-race-compensated.png`
   - Precondition: the saved workbench obtains a newer review revision after
     Context materialization but before receipt CAS
   - Visible state: revision error, zero checkpoints, and preserved newer
     review state
   - Durable mutation: the exact newly created checkpoint is compensated; the
     concurrent workbench revision is not overwritten

The script fails if the PTY is not 180×52 and true-color capable, the reviewed
session is not retained, a failed receipt leaves a checkpoint,
late success is mistaken for failure, interrupted recovery creates a duplicate,
or compensation overwrites a newer workbench revision.

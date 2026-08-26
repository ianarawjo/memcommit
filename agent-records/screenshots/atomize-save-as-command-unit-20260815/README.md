# Atomize Save As command-unit capture

This ordered replay records the forward-only Save As contract: Atomize keeps
its branch baseline as provenance, publishes only the final derived Context,
and represents that result as one `atomize` creation checkpoint. It also
records the exact failure/retry and lifecycle boundaries that make the single
checkpoint safe.

## Environment

- Capture date: 2026-08-15
- Command: `python agent-records/screenshots/atomize-save-as-command-unit-20260815/capture.py`
- PTY: real `pexpect` PTY, explicitly set and verified as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed
- Store: isolated temporary `MemoryStore` roots; no user Context was read or
  changed
- Provider: deterministic local all-ATOMIC provider; no network connection
- Provenance: every PNG is rendered from its color-preserving `.typescript`;
  the matching `.txt` is the final visible-canvas projection

## Ordered interaction log

1. `01-exact-save-location-review.png`
   - Command: `mem atomize --context atomize/source --save-as atomize/output`
   - Preceding input: none; one exact analysis/workbench already exists
   - Visible state: the exact `NOT CREATED` Save Location and explicit `y`
     creation boundary
   - Durable mutation: fixture analysis/workbench only; Output absent

2. `02-one-checkpoint-success.png`
   - Preceding key: `y`, then Enter
   - Visible state: final-only success receipt and one-checkpoint verification
   - Durable mutation: final Output, one `atomize` checkpoint, copied analysis,
     Source terminal receipt, and current selection

3. `03-read-only-final-result.png`
   - Child mode: reopen both Contexts and Trace with `create=False`
   - Visible state: distinct Source/Output UIDs, one Memory, only the `atomize`
     checkpoint, and recorded `CREATED → ATOMIZE_KEEP` lineage
   - Durable mutation: none

4. `04-one-command-undo.png`
   - Command: `mem undo`
   - Visible state: one Atomize command receipt; Output absent, receipt reversed,
     and current Context restored to Source
   - Durable mutation: Output Context/checkpoints/copied analysis moved to the
     validated command archive; Source workbench returned to reviewing state

5. `05-one-command-redo.png`
   - Command: `mem redo`
   - Visible state: one Atomize command receipt; same Output restored with its
     original history and terminal Source receipt
   - Durable mutation: archived Context and copied analysis restored; one Redo
     receipt appended; current selection restored when still eligible

6. `06-prepublication-failure.png`
   - Preceding key: `y`, then Enter
   - Precondition: injected transform failure before require-new publication
   - Visible state: Atomize error and explicit verification that Output remains
     absent
   - Durable mutation: none beyond the original analysis/workbench

7. `07-retained-output-retry-review.png`
   - Preceding key: first `y`, then Enter
   - Precondition: final Output/checkpoint publishes, then Source receipt write
     fails
   - Visible state: retained recoverable Output with exactly one checkpoint
     and an explicit pause before retrying that already-reviewed exact route
   - Durable mutation: final Output and copied analysis retained; Source receipt
     still reviewing; current remains Source

8. `08-retry-recovered.png`
   - Preceding key: Enter at the retry pause; no second creation approval is
     requested for the already-reviewed exact Output
   - Visible state: recovered-checkpoint notice and verification that the retry
     completed the Source receipt/current selection without another checkpoint
   - Durable mutation: missing receipt and selection only

The script fails if the terminal is not 180×52 and true-color capable, an
intermediate Context becomes visible, Save As creates more than one initial
checkpoint, Undo/Redo loses the Context identity or receipt, or retry creates a
duplicate checkpoint.

# Bare Atomize and applied Review capture

This ordered replay records the direct current-Context contract: bare
`mem atomize` does not open a session, applies one complete saved analysis in
place, prints representative full split content, and leaves that analysis
available in read-only `mem review atomize`.

## Environment

- Capture date: 2026-08-20
- Command: `python docs/screenshots/atomize-direct-current-review-20260820/capture.py`
- PTY: real `pexpect` PTY, explicitly set and verified as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed
- Store: isolated temporary `MemoryStore`; no user Context was read or changed
- Provider: deterministic local four-split Atomize provider; no network call
- Provenance: every PNG is rendered from its color-preserving `.typescript`;
  the matching `.txt` is the final visible-canvas projection

## Ordered interaction log

1. `01-direct-apply-receipt.png`
   - Exact command: `mem atomize`
   - Current Context: `atomize/direct-current`
   - Preceding input: none
   - Visible state: four splits summarized as eight children; the first three
     source/child groups show stable UIDs and full realistic Memory text, one
     additional split is handed to Review, and typed review-finding counts are
     zero
   - Durable mutation: one Context checkpoint and one terminal workbench
     receipt; four source Memories become eight children

2. `02-applied-review-entry.png`
   - Exact command: `mem review atomize`
   - Preceding input: none
   - Visible state: complete saved analysis opens with status `APPLIED`; no
     provider is called, each item title pairs its source UID with its actual
     content preview, and no editable Apply or response control is exposed
   - Durable mutation: none

3. `03-applied-split-detail.png`
   - Preceding keys: `Tab`, `Down`, `Enter`
   - Visible state: one saved split detail shows its exact Source Memory,
     classification, reason, and proposed children
   - Durable mutation: none

4. `04-read-only-verification.png`
   - Exact command: `mem review atomize --snapshot`
   - Precondition: the applied Review was closed with `q`
   - Invocation: separate diagnostic command; it does not appear automatically
     after closing the interactive Review
   - Visible state: the complete non-interactive Review snapshot plus durable
     verification of eight Memories, one checkpoint, and one terminal receipt
   - Durable mutation: none

The recorder fails if the terminal is not 180×52 and color-capable, bare
Atomize opens a session instead of completing, representative output omits its
handoff, applied Review is not marked read-only, or review changes the one
checkpoint/receipt pair.

# Bare Atomize and applied Review capture

This ordered replay records the direct current-Context contract: bare
`mem atomize` does not open a session, applies one complete saved analysis in
place, prints a compact receipt, and leaves that complete analysis
available in read-only `mem review atomize`.

## Environment

- Capture date: 2026-08-23
- Command: `python agent-records/screenshots/atomize-direct-current-review-20260820/capture.py`
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
   - Visible state: four splits are summarized as eight children with typed
     effect counts; three exact source-to-child effect groups are shown and one
     explicitly hands off to Review, followed by complete receipt/checkpoint
     identities, the exact Review route, and recovery
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
     classification, reason, and `APPLIED CHILD MEMORIES` as explicit
     `MEMORY n` rows rather than choice-like numeric markers
   - Durable mutation: none

4. `04-read-only-verification.png`
   - Exact command: `mem review atomize --snapshot`
   - Precondition: the applied Review was closed with `q`
   - Invocation: separate diagnostic command; it does not appear automatically
     after closing the interactive Review
   - Visible state: the complete non-interactive Review snapshot, including
     applied child Memory contents without repeated source-span evidence, plus
     durable verification of eight Memories, one checkpoint, and one terminal
     receipt
   - Durable mutation: none

The recorder fails if the terminal is not 180×52 and color-capable, bare
Atomize opens a session instead of completing, the compact receipt omits its
Review handoff, applied Review is not marked read-only, or Review changes the one
checkpoint/receipt pair.

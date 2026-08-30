# Atomize read-only findings and one-line receipt capture

This ordered replay records the current responsibility boundary: Impact owns
non-applying analysis, `mem atomize [TARGET]` applies the exact proposal in
place, Review owns the provider-free read-only report, and a focused Memory
target never adds its neighboring evidence to the replacement set.

## Environment

- Capture date: 2026-08-30
- Command: `python agent-records/docs/screenshots/atomize-read-only-findings-20260829/capture.py`
- PTY: real `pexpect` PTY, explicitly set and verified as `52 180`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed
- Profile/store: isolated temporary `MemoryStore`; no user Context was read or
  changed
- Current Context: `atomize/read-only-findings`
- Provider: deterministic local Atomize provider; no network call
- Provenance: every PNG is rendered from the actual color-preserving PTY
  `.typescript`; the matching `.txt` is the final visible-canvas projection

## Ordered interaction log

1. `01-analysis-read-only-findings.png`
   - Exact command: `mem impact atomize`
   - Preceding input: none
   - Visible state: `MEM IMPACT · ATOMIZE`, `ANALYSIS · NON-APPLYING`, two
     Source Memories, three findings, and three unresolved issues; there is no
     Output location, Apply control, or Responses frame
   - Durable mutation: analysis/review-record evidence only; no Context checkpoint

2. `02-ambiguity-read-only-detail.png`
   - Preceding keys: `Tab`, `Down`, `Enter`
   - Visible state: exact Source Memory, classification, reason, and possible
     readings for Ambiguity 1; readings are prose evidence, not selectable
     response controls
   - Durable mutation: none; closing the analysis leaves zero checkpoints

3. `03-apply-unresolved-issue-receipt.png`
   - Exact command: `mem atomize`
   - Precondition: exact compatible analysis from steps 1–2
   - Visible state: `UNRESOLVED ISSUES · 3 · APPLIED AS-IS`, followed by each
     ambiguity/conflict as one logical output line with exact Memory content
     and reason; terminal wrapping does not add semantic item boundaries
   - Durable mutation: one deliberate Atomize checkpoint and one terminal
     application record; both Source Memories are preserved

4. `04-applied-read-only-review.png`
   - Exact command: `mem review atomize`
   - Preceding input: none
   - Visible state: applied analysis evidence with `APPLIED RECORD · READ
     ONLY`; no Output location, Responses, or Apply control exists
   - Durable mutation: none

5. `05-applied-read-only-detail.png`
   - Preceding keys: `Tab`, `Down`, `Enter`
   - Visible state: the same immutable Ambiguity detail and possible readings
     after Apply
   - Durable mutation: none; closing with `q` leaves the checkpoint count at
     one

6. `06-read-only-verification.png`
   - Exact command: `mem review atomize --snapshot`
   - Precondition: the interactive Review was closed
   - Visible state: complete non-interactive evidence for all three findings
     and `READ-ONLY VERIFICATION · REVIEW RECORD UNCHANGED True · CHECKPOINTS 1`
   - Durable mutation: none; the legacy-schema review-record bytes before and
     after Review are identical

7. `07-focused-target-before.png`
   - Exact command: read-only setup projection for `atomize/focused-target`
   - Visible state: the composite selected Memory and its independent neighbor
   - Durable mutation: Context initialization for the isolated capture fixture;
     zero Atomize checkpoints

8. `08-focused-target-application.png`
   - Exact command: `mem atomize atomize/focused-target:UID_PREFIX`
   - Visible state: one selected source becomes two atomic Memories
   - Durable mutation: one Atomize checkpoint in the owning Context

9. `09-focused-target-verification.png`
   - Exact command: read-only Store projection after focused application
   - Visible state: both children plus the byte-identical unselected neighbor;
     `UNSELECTED NEIGHBOR PRESERVED True · CHECKPOINTS 1`
   - Durable mutation: none

The capture fails when the PTY is not 180×52 and true-color capable, when a
Responses frame appears, when the receipt omits the three unresolved issues,
when Review is not marked read-only, or when Review changes the one saved
checkpoint/workbench pair.

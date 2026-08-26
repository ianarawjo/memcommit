# Ticker v2 audit issues

## CORE · 105/105 counted commands

The frozen template had no dedicated ticker Context. To avoid uncounted
bootstrap commands, the lane reused five exact Contexts whose direct Memory
sets were verified empty before sequence 1. Exact/direct routes are clean
ticker evidence. Recursive routes below `task-2` and `task-3` deliberately
include their pre-existing local/granted descendants and are noisy-boundary
evidence, not clean ticker-only semantic results.

### TICK-V2-CONTEXTS-01 — Ticker orientation still requires a whole-Profile scan

- Expected: focus Context discovery on the ticker role Contexts while retaining
  current and Grant annotations.
- Actual: all five calls emitted the same 112-line whole-Profile catalog; the
  operation has no focus operand.
- Workaround: locate the five roles once, then use exact operands elsewhere.
- Severity: **Medium**.
- Classification: **usability / information overload**.
- Reproduction: **5/5**.
- Evidence: [round 1](raw/core/001-contexts-attempt-1.stdout.txt),
  [round 2](raw/core/022-contexts-attempt-2.stdout.txt),
  [round 3](raw/core/043-contexts-attempt-3.stdout.txt),
  [round 4](raw/core/064-contexts-attempt-4.stdout.txt), and
  [round 5](raw/core/085-contexts-attempt-5.stdout.txt).

### TICK-V2-CHUNK-RECEIPT-01 — Successful Chunk receipts omit created UIDs

- Expected: map the removed UID to every created UID so a later command can
  consume the split directly.
- Actual: four successful sentence, clause, punctuation, and length-bound
  splits ended with only `Done — N memories added`; no new UID appeared.
- Workaround: immediately List the exact Context and match fragments manually.
- Severity: **High**.
- Classification: **usability / output reuse**.
- Reproduction: **4/4 successful splits**; round 5 was an intentional missing
  selector.
- Evidence: [sentence](raw/core/014-chunk-attempt-1.stdout.txt),
  [clause](raw/core/035-chunk-attempt-2.stdout.txt),
  [punctuation](raw/core/056-chunk-attempt-3.stdout.txt), and
  [length-bound](raw/core/077-chunk-attempt-4.stdout.txt).

### TICK-V2-AMBIG-TIMEOUT-INFRA-01 — One ambiguity scan exceeded the provider ceiling

- Expected: return a validated report or an operation-owned provider error
  within the audit ceiling.
- Actual: the direct `task-1` scan emitted no result and the audit driver ended
  it after 240 seconds. Four other ambiguity attempts completed.
- Workaround: retain the frozen Source and retry in a later provider turn; no
  partial result exists.
- Severity/classification: **Infrastructure; not a product defect**.
- Reproduction: **1/5**.
- Evidence: [timeout](raw/core/082-find-ambiguities-attempt-4.stderr.txt) and
  [later successful control](raw/core/103-find-ambiguities-attempt-5.stdout.txt).

## Reviewed non-defects and campaign boundaries

- Recursive Summarize safely rejected historical Reference/live divergence for
  one Memory identity in sequences 50 and 92.
- Compare safely rejected empty or overlapping endpoint frames in sequences
  16, 58, 79, and 100; the disjoint Memory-to-Memory control succeeded.
- Recursive redundancy scans took 134.695 and 211.309 seconds because the
  borrowed task roots exposed 306 and 407 pre-existing descendant Memories.
  Those outputs are retained as deliberate noisy-boundary evidence.

The structured CORE ledger is [phase-core.json](phase-core.json), and its
machine-readable issue registry is [issues-core.json](issues-core.json).

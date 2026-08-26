# a-is-apple v2 · CORE phase issues

CORE completion: **105/105 counted commands** across 21 operations, five
interleaved methods each. There were 96 successful exits and nine nonzero
exits. Five nonzero exits were expected, atomic boundary controls (self/duplicate
Embed, same-Context Move, and identical-input Compare); four were repeated
unexpected Find Ambiguities failures. All 105 pre-state digests match the prior
attempt's post-state digest. The lane published 33 durable Context-tree
mutations without a reset.

The frozen template did not contain a dedicated `audit/a-is-apple` Context and
the campaign forbids uncounted initialization. Exact `practice` therefore served
as the empty starting namespace: it had zero direct Memories and no a-is-apple
Ground. Its pre-existing `practice/description` and `practice/source`
descendants are disclosed limitations; later direct changes to `source` were
limited to lane-local provenance/conflict experiments.

## AIA-V2-CONTEXTS-01 — World orientation still requires a whole-Profile scan

- Expected: a user growing one small world can narrow Context orientation to
  that world while retaining current/grant annotations.
- Actual: every `contexts` attempt emitted the same 112-row, 7,671-byte Profile
  inventory. The current `practice` row was visible, but this operation has no
  operand for focusing on the world.
- Workaround: visually locate `practice` once, then use explicit Context
  operands for other operations.
- Severity: **Medium**.
- Classification: **usability / information overload**.
- Reproduction: **5/5** attempts.
- Evidence: [round 1](raw/core/001-contexts-1.txt),
  [round 2](raw/core/022-contexts-2.txt),
  [round 3](raw/core/043-contexts-3.txt),
  [round 4](raw/core/064-contexts-4.txt), and
  [round 5](raw/core/085-contexts-5.txt).

## AIA-V2-CHUNK-RECEIPT-01 — Successful Chunk receipts omit all created Memory UIDs

- Expected: a mutating receipt names every new Memory so its output can feed
  Edit, Move, Reference, or another Chunk directly.
- Actual: all five three-way clause splits showed the proposed text and only
  `Done — 3 memories added`; no created UID appeared. A subsequent List or
  Show was required to recover selectors.
- Workaround: immediately run exact List or Show and match fragment bodies and
  placement.
- Severity: **Medium**.
- Classification: **usability / output reuse**.
- Reproduction: **5/5** successful splits.
- Evidence: [round 1](raw/core/015-chunk-1.txt),
  [round 2](raw/core/036-chunk-2.txt),
  [round 3](raw/core/057-chunk-3.txt),
  [round 4](raw/core/078-chunk-4.txt),
  [round 5](raw/core/099-chunk-5.txt), and the later
  [List UID recovery](raw/core/023-list-2.txt).

## AIA-V2-CHUNK-ATOMICITY-01 — Clause Chunk repeatedly creates context-dependent Memories

- Expected: each resulting Memory is independently meaningful or retains a
  typed relation to the neighboring fragments needed to interpret it.
- Actual: every split emitted dependent fragments, including `this edited
  duplicate retains the original`, `assertion.`, `copied from the original
  direct Memory for`, `provenance.`, and `unresolved alternatives remain
  explicit.` The first ambiguity review flagged one such fragment because its
  referent and retention meaning were unclear.
- Workaround: avoid clause Chunk for compact claims, or immediately review and
  repair/Meld the fragments before treating them as independent Memories.
- Severity: **High**.
- Classification: **semantic safety / context dependence**.
- Reproduction: **5/5** splits produced at least one dependent fragment.
- Evidence: the five Chunk captures above and
  [the successful ambiguity finding](raw/core/019-find-ambiguities-1.txt).

## AIA-V2-AMBIG-DECODE-01 — Find Ambiguities repeatedly loses the result on a NONE/question mismatch

- Expected: return a validated finding set or a stable empty report for the
  frozen Source frame.
- Actual: rounds 2–5 failed after provider work with `Codex find_ambiguities
  returned a question for NONE.` No usable report was returned. The active
  Context-tree digest remained unchanged, so each failure was atomic but no
  partial result was available.
- Workaround: preserve the Source frame and retry, or use Query/Find Conflicts
  for partial review. Four consecutive failed controls show that retry is not
  reliable here.
- Severity: **High**.
- Classification: **functional reliability / provider contract**.
- Reproduction: **4/5** attempts; round 1 was the successful control.
- Evidence: [successful control](raw/core/019-find-ambiguities-1.txt),
  [round 2 failure](raw/core/040-find-ambiguities-2.txt),
  [round 3 failure](raw/core/061-find-ambiguities-3.txt),
  [round 4 failure](raw/core/082-find-ambiguities-4.txt), and
  [round 5 failure](raw/core/103-find-ambiguities-5.txt).

## AIA-V2-SUMMARY-SALIENCE-01 — Recursive Summary drops the small world's direct mappings behind larger descendants

- Expected: a recursive summary of `practice` represents the direct root claims
  as well as the larger descendant policy corpus, especially after deliberate
  mapping conflicts become visible.
- Actual: rounds 2 and 4 summarized only the pre-existing editing/verification
  descendants. They omitted all direct a→apple claims in round 2 and all
  direct/root-visible a/b mappings and the b conflict in round 4. Adjacent
  Show, Find, and Query routes exposed that omitted evidence.
- Workaround: summarize each exact Context separately or ask a focused Query,
  then combine the results manually.
- Severity: **High**.
- Classification: **semantic fidelity / source salience**.
- Reproduction: **2/2** recursive summaries after mappings existed; the exact
  Source summary was a useful control.
- Evidence: [round 2 Show](raw/core/024-show-2.txt),
  [round 2 Summary](raw/core/028-summarize-2.txt),
  [round 4 Find](raw/core/067-find-4.txt),
  [round 4 Query](raw/core/069-query-4.txt),
  [round 4 Summary](raw/core/070-summarize-4.txt), and
  [round 5 exact Source control](raw/core/091-summarize-5.txt).

## Prior-audit regression notes

- Persisted: whole-Profile Context orientation; Chunk receipt UID omission;
  dependent clause fragments; and the Find Ambiguities NONE/question decoder
  failure. The decoder symptom worsened from 1/5 in the prior phase to 4/5 here.
- Not reproduced: Recursive List rendered each Context once when it was reached
  both lexically and by Embed, using `VIA EMBED` as the single route annotation;
  all five summaries stayed in English; and no clear Compare provenance
  association error was observed.
- Not retested: the prior accepted ancestor-Embed cycle. This phase's self-embed
  and duplicate-identity Embed controls were rejected atomically.

The authoritative structured ledger is [phase-core.json](phase-core.json), and
the machine-readable issue set is [issues.json](issues.json).

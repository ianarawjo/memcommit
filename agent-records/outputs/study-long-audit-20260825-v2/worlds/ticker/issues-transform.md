# Ticker Transform Issues

Reviewed TRANSFORM findings from the frozen v2 ticker lane.

## TICK-V2-T-ATOMIZE-WHOLE-01 — Whole-Context Atomize loses its review artifact when unresolved items survive repair

- Severity: `HIGH`
- Classification: `FUNCTIONAL_RELIABILITY_WHOLE_FRAME`
- Reproduction: 1/1 whole-Context attempt failed; 3/3 focused valid controls completed
- Expected: A complete dirty ticker frame saves an actionable Atomize analysis containing both the composite rule/example and the incomplete fragment, just as focused Atomize saves reviewable issues.
- Actual: The whole-frame call spent 28.3s, then failed because one item remained COMPOSITE and another UNCERTAIN; no session was saved. Three focused-Memory controls completed, and saved Atomize Impact later represented both issue types.
- Workaround: Atomize one Memory at a time and manually reconcile the saved sessions; preserve the whole-frame input because no failed-analysis artifact can be reopened.

Evidence:

- `worlds/ticker/raw/transform/003-atomize-1.txt`
- `worlds/ticker/raw/transform/027-atomize-2.txt`
- `worlds/ticker/raw/transform/051-atomize-3.txt`
- `worlds/ticker/raw/transform/064-impact-3.txt`
- `worlds/ticker/raw/transform/099-atomize-5.txt`

## TICK-V2-T-AUDIT-FRAGMENT-01 — Audit repeatedly reports zero ambiguities for a subjectless ticker fragment

- Severity: `HIGH`
- Classification: `SEMANTIC_FALSE_NEGATIVE_CROSS_OPERATION`
- Reproduction: 3/3 successful Audits whose snapshot contained the fragment
- Expected: The standalone Memory `becomes NORTHSTAR ...` is flagged as underspecified, or Audit records uncertainty consistently with Atomize over the same saved Source.
- Actual: All three Audits containing the fragment reported 0 ambiguities. Atomize over the same direct frame classified the fragment UNCERTAIN because the omitted subject prevents a standalone commitment; the conformance Audit itself also treated the fragment as a degraded case.
- Workaround: Run focused Atomize or manually inspect the Audit snapshot before accepting a zero-ambiguity summary.

Evidence:

- `worlds/ticker/raw/transform/003-atomize-1.txt`
- `worlds/ticker/raw/transform/004-audit-1.txt`
- `worlds/ticker/raw/transform/028-audit-2.txt`
- `worlds/ticker/raw/transform/064-impact-3.txt`
- `worlds/ticker/raw/transform/076-audit-4.txt`

## TICK-V2-T-DIFF-CURRENT-01 — Checkpoint Diff hides the destructive current state after Clear

- Severity: `HIGH`
- Classification: `SAFETY_RECOVERY_OBSERVABILITY`
- Reproduction: 5/5 post-Clear Diff attempts
- Expected: After Checkpoint, Delete/Clear, then `diff CHECKPOINT --context SCRATCH`, Diff shows the current empty scratch as removals from the checkpoint.
- Actual: All five calls rendered `THIS CHECKPOINT VS PREVIOUS` and reported every checkpointed item kept with zero removals, even though each immediately followed a successful Clear of 8 or 14 direct items.
- Workaround: Use an exact direct read to inspect current state, or create a second checkpoint solely to compare history; Revert remains the reliable recovery action.

Evidence:

- `worlds/ticker/raw/transform/007-clear-1.txt`
- `worlds/ticker/raw/transform/008-diff-1.txt`
- `worlds/ticker/raw/transform/031-clear-2.txt`
- `worlds/ticker/raw/transform/032-diff-2.txt`
- `worlds/ticker/raw/transform/055-clear-3.txt`
- `worlds/ticker/raw/transform/056-diff-3.txt`
- `worlds/ticker/raw/transform/079-clear-4.txt`
- `worlds/ticker/raw/transform/080-diff-4.txt`
- `worlds/ticker/raw/transform/103-clear-5.txt`
- `worlds/ticker/raw/transform/104-diff-5.txt`

## TICK-V2-T-ELABORATE-UNVERIFIED-01 — Elaborate applies invented examples despite an existing-provenance-only Goal

- Severity: `HIGH`
- Classification: `SEMANTIC_PROVENANCE_UNSUPPORTED_AUTOAPPLICATION`
- Reproduction: 1 source-bound existing-provenance-only route
- Expected: The exact Source plus Goal `Explain only existing ticker-example provenance` retains only observed examples, or stages any new hypothetical case for explicit acceptance.
- Actual: Elaborate labeled its output `UNVERIFIED · BEST_EFFORT` but immediately applied Route 066 and Acme Class A examples absent from the Source, alongside supported cases. The same-round checkpoint later removed them.
- Workaround: Run Elaborate only in checkpointed scratch, review every generated fact against Source, and Revert rather than retaining UNVERIFIED additions.

Evidence:

- `worlds/ticker/raw/transform/010-elaborate-1.txt`
- `worlds/ticker/raw/transform/019-revert-1.txt`

## TICK-V2-T-FORGET-INVERSION-01 — Forget reverses a do-not-remove numeral-preservation instruction

- Severity: `HIGH`
- Classification: `SEMANTIC_SAFETY_INSTRUCTION_INVERSION`
- Reproduction: 1/1 negated numeral-preservation instruction
- Expected: `remove no numeral rule that preserves source-supported digits` keeps both digit-preservation rules and their numeral qualifiers.
- Actual: Forget deleted the two Memories that explicitly preserved digits and leading zeroes, then edited two remaining rules to remove `numeral-containing` and `numeral-bearing`. It reported four applied changes. Revert restored the exact pre-round digest.
- Workaround: Treat a Forget receipt as a proposal, compare each disposition to the instruction, and immediately Revert when KEEP/DROP polarity is inverted.

Evidence:

- `worlds/ticker/raw/transform/057-distill-3.txt`
- `worlds/ticker/raw/transform/058-elaborate-3.txt`
- `worlds/ticker/raw/transform/062-forget-3.txt`
- `worlds/ticker/raw/transform/067-revert-3.txt`

## TICK-V2-T-MELD-PEER-01 — Meld loses the session when Compare repair returns invalid PEER sides

- Severity: `HIGH`
- Classification: `FUNCTIONAL_RELIABILITY_PROVIDER_RELATION_SCHEMA`
- Reproduction: 1 provider/repair path
- Expected: A plain independent Meld returns an exhaustive valid relation set or a stable reviewable failure artifact bound to the frozen peers.
- Actual: The only provider-executing plain setup spent 66.3s, then failed because a DISTINCT relation used invalid PEER sides. No Meld session was saved; the other routes correctly requested an initial plain setup.
- Workaround: Preserve both exact peer snapshots and retry the whole setup; there is no partial relation artifact to repair locally.

Evidence:

- `worlds/ticker/raw/transform/065-meld-3.txt`

## TICK-V2-T-MERGE-UID-HANDOFF-01 — Merge receipts omit every copied item mapping and UID

- Severity: `MEDIUM`
- Classification: `USABILITY_OUTPUT_REUSE`
- Reproduction: 3/3 Merges that copied new items; two later idempotent controls changed nothing
- Expected: A successful structural Merge receipt maps each source item to its target UID so later Delete, Trace, and automation can consume the result.
- Actual: Three changing Merges reported only aggregate NEW counts (6, 5, and 6) and no source-to-target item identity. The audit harness had to inspect target storage to select copied UIDs for later exact operations.
- Workaround: Run an exact target List after Merge and manually correlate content/order with Source.

Evidence:

- `worlds/ticker/raw/transform/001-merge-1.txt`
- `worlds/ticker/raw/transform/025-merge-2.txt`
- `worlds/ticker/raw/transform/049-merge-3.txt`
- `worlds/ticker/raw/transform/073-merge-4.txt`
- `worlds/ticker/raw/transform/097-merge-5.txt`

## TICK-V2-T-REVERT-OVERLOAD-01 — Large Revert receipts truncate the restoration manifest

- Severity: `MEDIUM`
- Classification: `USABILITY_RECOVERY_EVIDENCE`
- Reproduction: 3/3 receipts above the display threshold; two smaller receipts fit
- Expected: A recovery receipt exposes every affected direct item, or provides a machine-readable full manifest linked from the concise summary.
- Actual: Rounds 1, 2, and 5 ended their affected-content list with 2, 5, and 6 additional direct items not shown. Digest evidence proves exact recovery, but the person cannot audit every restoration from the receipt alone.
- Workaround: Use an exact direct read after Revert and compare against the checkpoint; retain the digest-level recovery ledger.

Evidence:

- `worlds/ticker/raw/transform/019-revert-1.txt`
- `worlds/ticker/raw/transform/043-revert-2.txt`
- `worlds/ticker/raw/transform/115-revert-5.txt`

## TICK-V2-T-SEVER-SUMMARY-01 — Sever discards the proposal when application-summary validation fails

- Severity: `HIGH`
- Classification: `FUNCTIONAL_RELIABILITY_PROVIDER_SUMMARY_SCHEMA`
- Reproduction: 2/5 Sever attempts
- Expected: Sever returns one complete validated proposal, or saves a reviewable failed-analysis artifact without changing Source or creating Result.
- Actual: Two of five identical semantic frames failed after 13.3s and 14.8s because the application summary cited an unchanged Source Memory or Criteria unrelated to a change. No session survived; three controls completed and Source remained unchanged.
- Workaround: Preserve the exact Source/Criteria digests and retry; successful sessions must still be reviewed before any result creation.

Evidence:

- `worlds/ticker/raw/transform/021-sever-1.txt`
- `worlds/ticker/raw/transform/045-sever-2.txt`
- `worlds/ticker/raw/transform/069-sever-3.txt`
- `worlds/ticker/raw/transform/093-sever-4.txt`
- `worlds/ticker/raw/transform/117-sever-5.txt`

## TICK-V2-T-UPDATE-SNAPSHOT-TRACEBACK-01 — Update crashes while copying an embedded ContextSnapshotRef into an application post-image

- Severity: `HIGH`
- Classification: `FUNCTIONAL_EXCEPTION_EMBEDDED_SNAPSHOT_APPLICATION`
- Reproduction: 1 exact direct target containing embedded Context snapshots
- Expected: Update applies or stages the reviewed typed edits, or returns an operation-owned concise error without partial publication.
- Actual: After producing two valid-looking edits, Update passed a ContextSnapshotRef to Context.from_dict and raised `KeyError: 'name'`, exposing a 2,639-line internal traceback. Pre/post Context-tree digests match, so no partial Context change was published.
- Workaround: Use a target without embedded snapshot items, or preserve the generated Impact plan and retry after isolating ordinary Memories; do not infer success from the pre-crash plan.

Evidence:

- `worlds/ticker/raw/transform/048-update-2.txt`

## TICK-V2-T-UPDATE-CONFLICT-AUTOAPPLY-01 — Update silently chooses one side of an explicit uppercase/lowercase Source conflict

- Severity: `HIGH`
- Classification: `SEMANTIC_SAFETY_UNRESOLVED_CONFLICT_AUTOAPPLICATION`
- Reproduction: 1 direct Update from the deliberately conflicting Criteria frame
- Expected: When Source contains both the uppercase core rule and a lowercase conflicting draft, Update surfaces a required resolution and does not mutate Target until the conflict is reviewed.
- Actual: Update edited the target punctuation Memory to require uppercase and applied it automatically, citing the uppercase rule but neither surfacing nor preserving the directly reachable lowercase draft. The immediately preceding saved Audit had classified those rules as a conflict.
- Workaround: Audit Source first, isolate only nonconflicting source evidence into a clean Context, and Update from that frame; retain the automatic checkpoint for undo.

Evidence:

- `worlds/ticker/raw/transform/052-audit-3.txt`
- `worlds/ticker/raw/transform/068-review-3.txt`
- `worlds/ticker/raw/transform/072-update-3.txt`

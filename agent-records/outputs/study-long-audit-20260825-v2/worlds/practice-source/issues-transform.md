# practice-source v2 transform findings

All 24 Transform operations ran five interleaved methods through the pinned world runner (120 counted commands). The Store was cumulative from CORE; `practice/source` remained byte-identical. Destructive trials stayed in lane-local scratch and each of five checkpoint windows was restored exactly.

## PS2-T-CONFORMANCE-SOURCE-TYPO — Conformance treats source-preserved typos as failures to preserve the source

- Expected: A rule requiring preservation of source meaning judges the supplied source as the reference frame and does not invent corrected protected wording that is absent from it.
- Actual: The direct source check marked 4/12 Memories nonconforming because `strucutre`, `redundent`, `titlle`, and `refferences` were misspelled, then claimed those exact source spellings failed exact preservation of corrected words that the source never contained.
- Workaround: Treat these four findings as reviewer-facing typo observations, not evidence that the source failed to preserve itself; use a separately declared spelling-correction rule when that is the intended check.
- Severity: **HIGH**
- Classification: **SEMANTIC_SELF_REFERENCE_FALSE_NEGATIVE**
- Reproduction: 1/1 direct source-meaning conformance route; four false-negative dispositions in one complete report
- Evidence: `worlds/practice-source/raw/transform/004-check-conformance-m1.txt`

## PS2-T-DIFF-CURRENT — Checkpoint Diff hides the destructive current state after Clear

- Expected: Immediately after checkpointing and clearing the same scratch Context, an explicit checkpoint Diff exposes the recoverable checkpoint versus the current empty state.
- Actual: Rounds 1, 2, and 4 cleared `practice/description`, but Diff rendered `THIS CHECKPOINT VS PREVIOUS`. Round 1 reported 13 kept and 0 removed; later rounds described older revision history rather than the current cleared state.
- Workaround: Verify current state separately with an exact read-only List/Show, retain the checkpoint UID, and use Revert for recovery; do not infer post-Clear state from checkpoint Diff.
- Severity: **HIGH**
- Classification: **SAFETY_RECOVERY_OBSERVABILITY**
- Reproduction: 3/3 same-target Checkpoint→Clear→Diff windows
- Evidence: `worlds/practice-source/raw/transform/003-checkpoint-m1.txt`, `worlds/practice-source/raw/transform/005-clear-m1.txt`, `worlds/practice-source/raw/transform/007-diff-m1.txt`, `worlds/practice-source/raw/transform/027-checkpoint-m2.txt`, `worlds/practice-source/raw/transform/029-clear-m2.txt`, `worlds/practice-source/raw/transform/031-diff-m2.txt`, `worlds/practice-source/raw/transform/075-checkpoint-m4.txt`, `worlds/practice-source/raw/transform/077-clear-m4.txt`, `worlds/practice-source/raw/transform/079-diff-m4.txt`

## PS2-T-ELABORATE-FABRICATED-SOURCE — Strict Elaborate fabricates quoted source instructions

- Expected: Strict elaboration from the inline anti-inference rule remains hypothetical or quotes only wording present in the supplied rule/source frame.
- Actual: The strict result introduced `Given the source instruction “Keep the heading exactly as supplied”` and `the sole source instruction “Preserve every technical term”`; neither quoted instruction exists in practice/source or the supplied inline rule. The receipt labels the results UNVERIFIED but writes them as source-grounded premises.
- Workaround: Keep the result in checkpointed scratch, rewrite examples parametrically, and verify every claimed source quotation against exact source UIDs before reuse.
- Severity: **MEDIUM**
- Classification: **SEMANTIC_PROVENANCE_FABRICATION**
- Reproduction: 2 fabricated quoted premises in the round-5 STRICT result
- Evidence: `worlds/practice-source/raw/transform/105-elaborate-m5.txt`

## PS2-T-DEDUN-RECEIPT — Dedun receipt hides survivor and absorption mappings

- Expected: A semantic cleanup that absorbs multiple items prints each survivor UID and absorbed-to-survivor link for immediate independent review and trace reuse.
- Actual: The late cleanup reported 4 absorbed, 4 kept, and 4 semantic DUN links, but printed no survivor UID or absorption mapping; only an aggregate checkpoint/review route remained.
- Workaround: Open the exact Review receipt immediately and compare an exact List/Trace before another mutation.
- Severity: **MEDIUM**
- Classification: **USABILITY_OUTPUT_REUSE_CONFIRMED_REGRESSION**
- Reproduction: 1/1 transforming Dedun result; four earlier no-redundancy controls required no mapping
- Evidence: `worlds/practice-source/raw/transform/108-dedun-m5.txt`

## PS2-T-GROUND-GRAMMAR — Ground binding grammar is discovered through sequential failures

- Expected: A binding attempt uses operation-consistent names or one validation failure prints the complete exact required form.
- Actual: `--publication-context` was rejected in favor of `--publication-target`; the corrected call then revealed that `--description` was also mandatory. The fully specified next route reached a separate independence boundary.
- Workaround: Supply name, goal, description, `--raw-context`, `--derived-context`, and `--publication-target` together, then ensure the three bound Context graphs are independent.
- Severity: **MEDIUM**
- Classification: **USABILITY_COMMAND_GRAMMAR_CONFIRMED_REGRESSION**
- Reproduction: Two sequential parser/validation failures
- Evidence: `worlds/practice-source/raw/transform/038-ground-m2.txt`, `worlds/practice-source/raw/transform/062-ground-m3.txt`, `worlds/practice-source/raw/transform/086-ground-m4.txt`

## PS2-T-IMPACT-ZERO-COVERAGE — Saved Meld Impact offers Apply with zero source coverage and zero changes

- Expected: A proposal with zero current Source coverage and no final Memories/changes foregrounds inapplicability or requires restart instead of presenting an Apply affordance.
- Actual: Impact reported READY_TO_APPLY, 0/2 Source coverage, 0 final Memories, and 0 changes, then rendered `[ APPLY? ] Continue to Meld Apply` without an equally prominent stale/inapplicable warning.
- Workaround: Do not apply the saved session; restart Meld against the current explicit target and re-check complete coverage.
- Severity: **HIGH**
- Classification: **SAFETY_STALE_PROPOSAL_DECISION_CONFIRMED_REGRESSION**
- Reproduction: 1 late saved-session Impact after cumulative target changes
- Evidence: `worlds/practice-source/raw/transform/088-meld-m4.txt`, `worlds/practice-source/raw/transform/111-impact-m5.txt`

## PS2-T-MELD-SNAPSHOT-RACE — Sequential Meld reports that a Source changed during Compare

- Expected: A strictly sequential explicit Source/target/Result command keeps its frozen sources stable or identifies a genuine external before/after revision.
- Actual: The Context-to-Context Meld ran for 49.69 seconds and failed that a Source changed while Compare was analyzing it. No audit command ran concurrently and no analysis was saved; directional inline Meld controls completed.
- Workaround: Retain the failure evidence and use a narrow inline Memory plus explicit baseline and `--restart`; avoid spending another whole-frame provider turn without a new snapshot.
- Severity: **HIGH**
- Classification: **FUNCTIONAL_SNAPSHOT_SELF_INVALIDATION_CONFIRMED_REGRESSION**
- Reproduction: 1 sequential whole-Context route; three directional inline controls succeeded
- Evidence: `worlds/practice-source/raw/transform/016-meld-m1.txt`, `worlds/practice-source/raw/transform/040-meld-m2.txt`, `worlds/practice-source/raw/transform/064-meld-m3.txt`, `worlds/practice-source/raw/transform/088-meld-m4.txt`

## PS2-T-MIXED-EVIDENCE-DEAD-END — Cumulative live evidence makes Ground, Meld, Sever, and Update unusable without a clean-room copy

- Expected: Exact selectors such as `--source-memory`, `--direct`, `--source-root-only`, and `--criteria-root-only` can safely narrow to eligible owned Memories while unrelated live References/Embeds remain visible evidence.
- Actual: Once scratch contained source References/Embeds, all five Updates failed graph-overlap checks even with exact source/target Memory selectors; four Sever routes rejected live References; a fully bound Ground rejected dependent Contexts; and late directional Meld rejected two otherwise unrelated direct References before inference.
- Workaround: Copy only intended owned Memories into new independent lane-local Contexts, retaining an external source-UID mapping, then run the transform there. This adds a clean-room preparation step and separates visible evidence from execution.
- Severity: **MEDIUM**
- Classification: **WORKFLOW_INTEROPERABILITY_MIXED_ITEM_TOPOLOGY**
- Reproduction: 11/11 executable routes exposed the same accumulated graph/item-family boundary
- Evidence: `worlds/practice-source/raw/transform/021-sever-m1.txt`, `worlds/practice-source/raw/transform/024-update-m1.txt`, `worlds/practice-source/raw/transform/045-sever-m2.txt`, `worlds/practice-source/raw/transform/048-update-m2.txt`, `worlds/practice-source/raw/transform/069-sever-m3.txt`, `worlds/practice-source/raw/transform/072-update-m3.txt`, `worlds/practice-source/raw/transform/086-ground-m4.txt`, `worlds/practice-source/raw/transform/096-update-m4.txt`, `worlds/practice-source/raw/transform/112-meld-m5.txt`, `worlds/practice-source/raw/transform/117-sever-m5.txt`, `worlds/practice-source/raw/transform/120-update-m5.txt`

## PS2-T-REVERT-OVERLOAD — Every large Revert receipt truncates its restoration manifest

- Expected: A large recovery remains compact while exposing a complete machine-reusable effect manifest or an exact non-mutating follow-up command.
- Actual: All five Reverts affected more than 12 direct items and printed only 12 previews followed by 2–29 omitted items. Counts and a recovery checkpoint remained, but the receipt alone could not verify every restored/removed identity.
- Workaround: Retain the exact checkpoint UID and verify the restored Context separately with List/Diff/Trace; treat the Revert receipt as aggregate evidence only.
- Severity: **MEDIUM**
- Classification: **USABILITY_RECOVERY_EVIDENCE_CONFIRMED_REGRESSION**
- Reproduction: 5/5 recovery windows
- Evidence: `worlds/practice-source/raw/transform/019-revert-m1.txt`, `worlds/practice-source/raw/transform/043-revert-m2.txt`, `worlds/practice-source/raw/transform/067-revert-m3.txt`, `worlds/practice-source/raw/transform/091-revert-m4.txt`, `worlds/practice-source/raw/transform/115-revert-m5.txt`

## PS2-T-TRACE-LIMIT — JSON Trace ignores the requested one-operation limit

- Expected: `trace --json --limit 1` bounds lineage-affecting command units to one, consistent with the documented Trace operation-limit contract.
- Actual: The response was 705 lines / 43,339 bytes and returned the full three-Member component plus multiple events, analyses, spans, and children despite `--limit 1`.
- Workaround: Parse only the needed JSON fields or use plain Trace for a bounded human receipt; do not assume JSON payload size follows `--limit`.
- Severity: **MEDIUM**
- Classification: **FUNCTIONAL_OUTPUT_BOUND_CONFIRMED_REGRESSION**
- Reproduction: 1 direct minimal-limit JSON route
- Evidence: `worlds/practice-source/raw/transform/094-trace-m4.txt`

## Positive controls and closed prior observations

- Distill no longer emitted the prior inferred prose-style meta-rule in its successful direct runs; rounds 3 and 4 instead failed closed when proposed rules did not fit the declared Goal.
- Diff's explicit checkpoint grammar now worked noninteractively; the remaining issue is its historical comparison semantics after a destructive current-state change.
- Elaborate consistently labeled generated cases UNVERIFIED, and Atomize never applied a split in this phase. Review's four `PENDING` failures were audit-orchestrator receipt-parsing limitations, not product failures; the stale round-5 Atomize Review correctly failed closed.
- Audit's conflict result differed from the independent CORE conflict turn, but separate semantic-provider judgments remain accepted variance; the independently self-contradictory CORE Conflict disposition remains the actionable defect.
- Missing selectors, self-Merge, stale Review, invalid session IDs, and failed Goal-fit proposals produced no partial mutation.

## Safe outcome

`practice/source` stayed at SHA-256 `3c7872e184194b45295052ec4efe40c9088f1b962e12fd4d30cfd2aeed7de212`. All five `practice/description` Reverts matched their round checkpoint digest. No external Share, clipboard, destructive source Apply, product-code edit, or TUI replay occurred.

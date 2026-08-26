# practice-source v2 core findings

The core phase executed all 21 assigned operations five times through the
pinned `run_world_mem.py practice-source` route. `practice/source` remained
byte-identical (`3c7872e1…ed7de212`) across all 105 attempts. Mutations were
confined to the lane-local `practice` and `practice/description` scratch
Contexts. No product code or external state was changed.

## PS2-CHUNK-CONTEXT-LOSS — Sentence splitting makes three constraints unsafe to review independently

- Expected: Chunking used as preparation for semantic atomization keeps each
  applicability trigger, protected object, exception, and companion safeguard
  with the action it governs.
- Actual: Sequence 36 detached `Change only wording that causes a problem.`
  from the authorized-polishing trigger. Sequence 57 detached the 20–30%
  fixed-limit action from its all-points and claim-strength safeguards.
  Sequence 78 left `preserve the intended word for.` without a complete
  protected object/context.
- Downstream evidence: Ambiguities flagged the percentage baseline at sequence
  61 and the incomplete title rule at sequences 82 and 103. Show rendered the
  detached safeguard/title fragments at sequences 66 and 87. Conflicts at
  sequence 104 then asked whether intended points or claim conditions may be
  sacrificed to meet the split reduction target.
- Workaround: Do not treat sentence/clauses Chunk as semantic atomization.
  Keep the polishing trigger with its edit boundary, the fixed-limit action
  with both preservation safeguards, and the title default/override with the
  literal protected word. Retain source provenance on every proposed atom.
- Severity: **P1 / high** meaning-preservation risk.
- Classification: **Semantic safety · confirmed regression** of prior
  `PS-CHUNK-CONTEXT-LOSS`.
- Evidence: `raw/core/036-chunk-m2.txt`, `057-chunk-m3.txt`,
  `061-find-ambiguities-m3.txt`, `066-show-m4.txt`, `078-chunk-m4.txt`,
  `082-find-ambiguities-m4.txt`, `087-show-m5.txt`,
  `103-find-ambiguities-m5.txt`, `104-find-conflicts-m5.txt`.

## PS2-CONFLICT-SELF-CONTRADICTION — Conflict classification contradicts its own reason

- Expected: A `CONFLICT` disposition identifies an incompatible pair; a pair
  that the analysis itself finds compatible is excluded or classified as not
  a conflict.
- Actual: Sequence 41 labeled title terminology versus sentence-case
  capitalization as `CONFLICT 9/9`, but its Reason says verbatim, `There is no
  semantic conflict.` The same run flagged 9/66 pairs, several of which combine
  separately triggered request modes rather than simultaneous requirements.
- Workaround: Read every Reason and manually discard a reported Conflict when
  the explanation says the pair is compatible. Do not alter source rules from
  the headline count alone.
- Severity: **P1 / high** semantic-review and unintended-rewrite risk.
- Classification: **Functional semantic defect · new in v2 run**. The prior
  audit returned zero direct-source conflicts, so this also exposes provider
  result instability at the decision boundary.
- Evidence: `raw/core/041-find-conflicts-m2.txt`.

## PS2-CHUNK-RECEIPT — Successful multi-chunk receipts omit reusable identities

- Expected: A successful split prints every created UID and complete text so
  each result can immediately feed Show, Edit, Move, and quality review.
- Actual: Sequences 36, 57, and 78 all said only `Done — 2 memories added`,
  omitted both UIDs, and truncated both previews (including mid-word cuts).
- Workaround: Run List on the exact Context and manually match complete text,
  then reuse the discovered UID. This audit used sequences 44/45, 65/66, and
  86/87 as the counted recovery path.
- Severity: **P2 / medium-high** traceability and re-entry cost.
- Classification: **Usability/receipt defect · confirmed regression** of prior
  `PS-CHUNK-RECEIPT`.
- Evidence: `raw/core/036-chunk-m2.txt`, `044-list-m3.txt`,
  `045-show-m3.txt`, `057-chunk-m3.txt`, `066-show-m4.txt`,
  `078-chunk-m4.txt`, `086-list-m5.txt`, `087-show-m5.txt`.

## PS2-MULTIROOT-COVERAGE — Search does not report zero-contribution roots

- Expected: Multi-root Search reports a disposition per requested root so a
  reviewer can distinguish not searched, no hit, and ranked out by a global
  limit.
- Actual: Sequence 47 requested source plus practice but returned only source.
  Sequence 68 again returned only source. Sequence 89 requested source,
  practice, and description but returned only two practice fragments; it
  omitted the already known damaged title chunk in description and gave no
  status for either missing root.
- Workaround: Search each exact Context independently and reconcile results
  manually before drawing a coverage conclusion.
- Severity: **P2 / medium-high** completeness risk.
- Classification: **Information coverage · confirmed regression** of prior
  `PS-MULTIROOT-COVERAGE`.
- Evidence: `raw/core/047-search-m3.txt`, `068-search-m4.txt`,
  `089-search-m5.txt`.

## PS2-SUMMARY-EVIDENCE-OMISSION — DIRECT summaries silently exclude direct References and Embeds

- Expected: A summary of a Context containing ordinary Memories, References,
  and live Context Embeds either incorporates readable evidence or states the
  excluded item types.
- Actual: Sequences 28, 49, 70, and 91 summarized ordinary Memories while
  excluding directly listed References and Embeds. `STATUS · DIRECT` did not
  explain that direct means only ordinary Memory input rather than all direct
  items visible in List.
- Workaround: Treat Summary as an ordinary-Memory orientation view. Use List,
  Show, Query, and Compare to inspect Reference and Embed evidence separately.
- Severity: **P2 / medium-high** evidence-completeness risk.
- Classification: **Information transparency · confirmed regression** of prior
  `PS-SUMMARY-REFERENCE-LOSS`.
- Evidence: `raw/core/023-list-m2.txt`, `028-summarize-m2.txt`,
  `049-summarize-m3.txt`, `070-summarize-m4.txt`,
  `086-list-m5.txt`, `091-summarize-m5.txt`.

## PS2-QUALITY-SCOPE-MISMATCH — Sibling direct-scope counts remain opaque

- Expected: Duplicate and redundancy receipts explain whether References and
  Context Embeds count as direct inputs and expose comparable corpus summaries.
- Actual: On the same early `practice` state, Duplicates checked 3 direct items
  while Redundancies checked 1 direct memory (sequences 17–18). On the same
  late `practice/description` state, the counts were 10 versus 8 (sequences
  80–81). The distinction is plausible but not explained in either receipt.
- Workaround: Infer that Duplicates considers all structural direct items while
  Redundancies sends only ordinary Memories to semantic analysis, then confirm
  actual item types with List.
- Severity: **P2 / medium** mental-model and cross-command comparison cost.
- Classification: **Usability/contract opacity · confirmed regression** of
  prior `PS-QUALITY-SCOPE-MISMATCH`.
- Evidence: `raw/core/017-find-duplicates-m1.txt`,
  `018-find-redundancies-m1.txt`, `080-find-duplicates-m4.txt`,
  `081-find-redundancies-m4.txt`.

## PS2-FIT-OPAQUE — Positive Fit has no evidence or source-to-target mapping

- Expected: Fit identifies which source constraints fit which target items and
  highlights missing triggers, provenance, or exceptions.
- Actual: All five attempts printed only `FIT · YES` and the two Context names.
  It remained YES after Ambiguities had proved an incomplete title rule and
  Conflicts had exposed a split fixed-limit/safeguard interaction.
- Workaround: Use Query, Compare, Show, Ambiguities, Conflicts, and source UIDs
  to build the mapping manually. Do not interpret Fit YES as proof that a
  candidate preserves meaning.
- Severity: **P2 / medium-high** false-confidence and explainability risk.
- Classification: **Semantic explainability · confirmed regression** of prior
  `PS-FIT-OPAQUE`.
- Evidence: `raw/core/021-fit-m1.txt`, `042-fit-m2.txt`,
  `063-fit-m3.txt`, `084-fit-m4.txt`, `105-fit-m5.txt`.

## PS2-CTX-OVERLOAD — Context discovery cannot narrow to the working subtree

- Expected: A practice workflow can inventory the `practice` subtree while
  retaining hierarchy and Grant annotations.
- Actual: Every Contexts attempt printed the same 112 visible rows for the
  whole Profile. The three practice rows were followed by task-1/task-2/task-3
  trees and Grants; the command had no prefix/subtree operand. Scratch content
  growth was invisible, so the five temporal checks produced identical output.
- Workaround: Scan once for the `practice` prefix, then carry exact names into
  scoped commands.
- Severity: **P2 / medium** repeated navigation and information-overload cost.
- Classification: **Usability/information overload · confirmed regression** of
  prior `PS-CTX-OVERLOAD`.
- Evidence: `raw/core/001-contexts-m1.txt`, `022-contexts-m2.txt`,
  `043-contexts-m3.txt`, `064-contexts-m4.txt`, `085-contexts-m5.txt`.

## PS2-QUERY-REFERENCE-OVERLOAD — Exhaustive answers bury the reusable atom list

- Expected: A broad Query may preserve exhaustive coverage while foregrounding
  a compact candidate list and exposing structured/reusable source mappings.
- Actual: Sequence 69 expanded a defaults question to all 12 Memories and 12
  inline References. Sequence 90 produced a strong atomization proposal but
  again printed all 12 full References across 44 captured lines and did not
  emit a reusable proposed-atom-to-source-UID structure.
- Workaround: Save the prose manually and return to source UIDs with List/Show,
  or issue narrower questions per constraint family.
- Severity: **P3 / low-medium** output-volume and reuse cost.
- Classification: **Usability/information density · confirmed regression** of
  prior `PS-QUERY-REFERENCE-OVERLOAD`.
- Evidence: `raw/core/069-query-m4.txt`, `090-query-m5.txt`.

## Boundaries that behaved correctly

- Duplicate Embed was rejected before mutation at sequence 74; pre/post target
  digests match, and the later List shows only the original source edge.
- The documented indirect Embed cycle was accepted at sequence 95; recursive
  Duplicates at sequence 101 terminated finitely after three Context identities.
- Add, Copy, Reference, Edit, and Move all returned reusable identities and
  kept every mutation in scratch. The no-match Replace at sequence 98 was a
  clean no-op.
- The prior inconsistent-summary-language issue did not recur: all five
  summaries were in English. The prior broad Replace surprise did not recur;
  the only broad candidate-label replacement in this run matched one Memory.

## Safe handoff to transform/Atomize

Atomization must keep each permission trigger with its action, fixed-limit
reduction with all-points and claim-strength safeguards, title defaults with
their narrow style-guide exception and protected literal word, and citation
verification with the review-before-rewrite boundary. The source fixture is
untouched; scratch contains deliberately damaged examples and must not be
treated as an approved atomized result.

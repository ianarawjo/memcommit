# practice-source phase-core issues

## PS-CHUNK-CONTEXT-LOSS — Mechanical sentence splitting makes constraints unsafe to review independently

- Expected: A preparation workflow for later atomization preserves every rule’s applicability trigger, protected object, exception, and necessary companion safeguard so each output can be reviewed without reconstructing its neighbors.
- Actual: Splitting the polishing candidate separated “Change only wording that causes a problem” from “during authorized polishing.” Quality analysis then treated the detached wording rule as potentially conflicting with capitalization and italics rules. Splitting the title candidate left “preserve the intended word for” without an object. Splitting the fixed-limit candidate separated the 20–30% target from its all-points/claim-strength safeguard; later conflict analysis asked whether intended points may be removed to meet the limit.
- Workaround: Do not use sentence/clauses chunking as semantic atomization. The later semantic phase must keep the polishing trigger with its edit boundary, the literal protected word `for` with its object, and the fixed-limit target with the no-strengthening/all-points safeguard. Each result must retain source provenance.
- Severity: **P1 / high** meaning-preservation risk.
- Reproduction: **Yes, 3 successful two-sentence splits**. Downstream Show, Ambiguities, and Conflicts independently exposed the damage.

## PS-CHUNK-RECEIPT — Successful split does not identify created Memories

- Expected: A mutating receipt prints every created UID and complete text so its outputs can feed `show`, `edit`, `move`, and quality review directly.
- Actual: All three two-Memory receipts said only “Done — 2 memories added,” omitted both UIDs, and truncated preview text mid-word. Each next round needed a separate `list` plus manual text matching to discover the results.
- Workaround: Run `list` on the exact target Context immediately after every split, then manually match the complete text before using a UID.
- Severity: **P2 / medium-high** traceability, output-reuse, and re-entry cost.
- Reproduction: **Yes, 3/3 actual multi-chunk mutations**.

## PS-SUMMARY-REFERENCE-LOSS — Direct summary silently excludes linked evidence

- Expected: When a Context visibly contains ordinary Memories, snapshot References, and embedded evidence, Summary either incorporates all readable evidence or clearly states which item types were excluded so completeness is not inferred.
- Actual: Review summaries recombined the ordinary split Memories but omitted the original-source lookup, fixed-limit, protected terminology, connector, and citation-verification References. The final summary did not mention those omissions; `STATUS · DIRECT` did not explain that “direct” means ordinary Memories only rather than all directly displayed items.
- Workaround: Treat Summary as an ordinary-Memory orientation view only. Use `list`, `show`, Query, and Compare to audit References and embedded Contexts separately.
- Severity: **P2 / medium-high** evidence-completeness risk.
- Reproduction: **Yes, rounds 3, 4, and 5** on increasingly evidence-rich Contexts.

## PS-SUMMARY-LANGUAGE — English source unexpectedly summarizes in Korean

- Expected: With an English source and no explicit language instruction, Summary keeps the source/session language or exposes a language choice.
- Actual: The round-2 summary of the single English copied Memory returned entirely in Korean. Other summaries in the same phase returned English.
- Workaround: Retry with an explicit language requirement through an operation that accepts a question, or manually translate while retaining the exact source.
- Severity: **P3 / low-medium** consistency and review cost.
- Reproduction: **No, 1 occurrence**; later summaries returned English.

## PS-MULTIROOT-COVERAGE — Multi-root Search hides branches with no returned result

- Expected: A search across multiple explicit Contexts reports coverage per requested root, including zero-result roots, so a reviewer can distinguish “not searched,” “searched with no hit,” and “ranked out by the global limit.”
- Actual: Round 3 returned only `practice/source` despite also requesting `review`; round 4 returned only source despite also requesting candidates. The final three-root diagnostic returned two damaged workspace Memories, omitted source companions and another known damaged atom, and provided no branch disposition.
- Workaround: Search each exact Context independently and reconcile the result sets manually before applying a cross-source limit.
- Severity: **P2 / medium** completeness and repeated-exploration cost.
- Reproduction: **Yes, 3 different multi-root searches**.

## PS-REPLACE-BROAD-MATCH — Context-wide substring replace changes unrelated labels without review

- Expected: A replacement intended for one candidate can target that exact Memory or preview every affected Memory before mutation.
- Actual: Replacing `CANDIDATE` with `DEFAULT CANDIDATE` in review matched two Memories. It changed the new title candidate as intended and also changed the older `REVIEW CANDIDATE` label to `REVIEW DEFAULT CANDIDATE`. The receipt gave counts but no per-Memory before/after list.
- Workaround: Run exact Find first, isolate the intended Memory in a dedicated Context, or use `edit` on its UID rather than Context-wide Replace.
- Severity: **P2 / medium** mutation-scope risk; the source fixture was not affected.
- Reproduction: **One broad-match event**; earlier single-match and final no-match trials establish its boundary.

## PS-QUALITY-SCOPE-MISMATCH — Sibling quality commands report incompatible direct cardinalities

- Expected: Duplicate and redundancy commands explain whether References and embedded Context edges count as “direct items,” and expose comparable corpus summaries.
- Actual: On the same round-1 Context, Duplicates checked 3 direct items while Redundancies checked 1 direct memory. On round-4 review, the counts were 8 versus 4. Recursive Duplicates repeatedly printed one empty section per workspace Context, while Redundancies silently excluded non-ordinary items from its count.
- Workaround: Read “items” as a broader structural catalog and “memories” as ordinary semantic inputs, then use List to reconstruct the exact corpus. This distinction is inferred from behavior, not explained in the receipts.
- Severity: **P2 / medium** mental-model and evidence-comparison cost.
- Reproduction: **Yes, 2 exact same-Context pairs**, plus 3 recursive duplicate runs.

## PS-FIT-OPAQUE — Positive Fit supplies no evidence or mapping

- Expected: A positive Fit result identifies which source constraints fit which target candidates, and highlights missing triggers, exceptions, or provenance needed for safe atomization.
- Actual: Every successful call printed only `FIT · YES` and target Context names, even when Ambiguities and Conflicts proved that split candidates had lost essential boundaries.
- Workaround: Use Query, Compare, Ambiguities, Conflicts, exact Show, and source References to build the mapping manually. Never treat FIT YES as evidence that an atom preserves meaning.
- Severity: **P2 / medium-high** explainability and false-confidence risk.
- Reproduction: **Yes, 4 successful rounds**; round 2 separately failed correctly on an empty direct candidate frame.

## PS-CTX-OVERLOAD — Global inventory obscures the small practice workspace

- Expected: Practice-source work can narrow Context discovery to `practice` while retaining hierarchy and access annotations.
- Actual: Every `contexts` attempt printed the full Profile, including all task-1/2/3 Contexts and Grants. The relevant seven practice names occupied only a small part of an approximately eight-screen output.
- Workaround: Scan once for the `practice` prefix and carry explicit Context names forward.
- Severity: **P2 / medium** repeated navigation and information-overload cost.
- Reproduction: **Yes, 5/5 rounds**.

## PS-QUERY-REFERENCE-OVERLOAD — Complete synthesis buries the next atomization action

- Expected: A broad Query can preserve exhaustive source coverage while foregrounding a compact proposed atom list and making References collapsible or separately reusable.
- Actual: The defaults/conditions Query and final atomization Query used all 12 source Memories and printed long inline Reference sections. The final answer was semantically strong, but required roughly ten terminal screens and did not emit a machine-reusable candidate/UID mapping.
- Workaround: Save the prose manually, then return to Find/List/Show by the displayed source UIDs. Run narrower Queries when only one constraint family is needed.
- Severity: **P3 / low-medium** output volume and reuse cost.
- Reproduction: **Yes, 2 all-source Queries**.

## PS-STATUS-CURRENT-ONLY — Status remains outside safe parallel coverage

- Expected: A parallel worker can inspect practice-source status with an explicit Context without relying on shared current state.
- Actual: Status has no explicit Context route. A successful attempt would describe global current rather than the source/workspace pair and therefore cannot be safely counted by this worker.
- Workaround: Root owns five serialized Status attempts while it controls the shared current Context.
- Severity: **P2 / medium** parallel-audit limitation.
- Reproduction: **Structural CLI contract; excluded from all 105 counted trials as instructed**.

## Safe handoff to the semantic phase

The source fixture was never mutated, and Atomize was intentionally not run. The prepared handoff is:

- keep review-only versus editing authorization attached to every editing constraint;
- preserve exact protected terminology and the literal intended word `for`;
- keep the fixed-limit 20–30% target coupled with all-points and no-strengthening safeguards;
- keep narrow style-guide overrides attached only to their corresponding defaults;
- retain full-source/citation verification and review-before-rewrite boundaries together;
- attach exact source provenance to every proposed atom.

The final audit Memory is `practice/audit-workspace/archive:5b1d1cb6`; source copies, snapshot References, and embeds remain available for independent review.


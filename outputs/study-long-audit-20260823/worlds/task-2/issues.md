# task-2 phase-core issues

## T2-STATUS-01 — Status cannot target an explicit Context

- Expected: In a shared-Profile parallel audit, `status` can inspect `task-2/participant/proposal-workspace` without depending on or changing the global current Context.
- Actual: `mem status task-2/participant/proposal-workspace` exits 2 because `status` accepts no Context operand. A successful attempt would therefore be current-only and unsafe for this parallel phase.
- Workaround: Exclude `status` from this parallel worker and let the root run its five attempts while task-2 is temporarily current in a serialized phase.
- Severity: High for parallel multi-world audits; no data corruption observed.
- Reproduction: Observed once here; structural CLI contract makes it deterministic. Root will own repeated evidence.

## T2-CONTEXTS-01 — Whole-Profile inventory obscures one world's Contexts

- Expected: A user working on task-2 can narrow the inventory to its local and granted subtree while retaining ownership/access annotations.
- Actual: `mem contexts` prints the complete 65-owned/43-granted shared Profile inventory and has no task filter, so task-2 orientation requires scanning several screens.
- Workaround: Search the terminal output for the `task-2` prefix and use explicit Context operands on subsequent commands.
- Severity: Medium usability and repeated-navigation cost.
- Reproduction: Reproduced 5/5 rounds. The durable task-2 contents changed, but every invocation still required scanning the same whole-Profile catalog.

## T2-SHOW-01 — Recursive combined view overwhelms the next synthesis action

- Expected: The combined recursive view makes source balance and the next useful comparison visible without requiring a full-corpus reread.
- Actual: The baseline recursive command rendered 35 Contexts and 300 Memories (roughly 700 lines). After local synthesis and an ancestor embed, the same route rendered 36 Contexts and 310 Memories in 602 captured lines. Both advisors are present equally, but the next synthesis action and cross-source relationships are buried.
- Workaround: Use targeted `find`, `search`, `compare`, and category-level Contexts after the initial completeness check.
- Severity: Medium usability and time cost.
- Reproduction: Reproduced twice with materially different accumulated states. Exact category-level `show` was the successful low-cost workaround.

## T2-CHUNK-01 — Chunk receipt does not identify created Memories

- Expected: A mutating receipt names every created UID so its output can be reused by later `edit`, `move`, `reference`, or review operations; preview clipping should be visibly distinguished from stored content.
- Actual: Every `chunk` receipt reported only the number of Memories added, never their UIDs. Fixed-width previews visually cut words at the right edge, although follow-up lookup showed that this part was display clipping rather than stored mid-word corruption.
- Workaround: Run a scoped `list`/`show`/`find` afterward and manually identify the new Memories by text.
- Severity: Medium workflow/reuse risk.
- Reproduction: Reproduced 5/5 attempts across sentence and clause methods, two Contexts, and early/late states.

## T2-QUALITY-FLAGS-01 — Related quality commands expose incompatible scope/output flags

- Expected: Closely related `find-*` operations accept a learnable common grammar for direct/recursive scope and plain output, or clearly explain their deliberate differences.
- Actual: `find-duplicates` and `find-redundancies` rejected `--plain`; `find-ambiguities` and `find-conflicts` rejected `--direct`. The initial recovery path therefore required operation-specific rediscovery before any analysis ran.
- Workaround: Retry each operation with only its supported flags and record the semantic scope from the receipt.
- Severity: Medium usability; first attempts performed no mutation.
- Reproduction: Four sibling commands reproduced the incompatible grammar in round 1. Supported routes then succeeded in rounds 2–5.

## T2-EMBED-COLLISION-01 — A successful granted embed breaks direct `show` on an already projected target

- Expected: When a target already exposes a READ-granted Context as a process-level readable projection, `embed` should either reject the duplicate before mutation or persist it idempotently so all direct readers continue to work.
- Actual: `mem embed task-2/advisor1 --into task-2/participant/proposal-workspace` succeeded and persisted item `fdc991fe`. The next `show --direct` on that target failed with `A granted view identity collides with an existing direct item.` The source was READ grant `293270b2` revision 1 and explicitly included EMBED authority. `list --direct` and `find --direct` on the same target still succeeded, and `show --recursive` later succeeded through its merged loader, so the break is command/scope-specific. A control embed of advisor2 into fresh target `task-2/participant` also succeeded and its direct `show` worked because that target did not already project the same identity. A QUERY-only source was separately rejected before mutation.
- Workaround: Do not persist a grant that the target already projects. For the affected target, use `list --direct`, `find --direct`, `show --recursive`, or show the granted source Context exactly; none is a complete substitute for a compact direct show.
- Severity: P1 candidate / High. A successful authorized mutation disables a primary read route with no warning in its receipt.
- Reproduction: One breaking target plus one fresh-target control and a four-command scope matrix. The exact duplicate-projection precondition was available only on the fixed workspace.

## T2-EMBED-CYCLE-01 — Embedding a lexical ancestor creates a non-obvious recursive reach cycle

- Expected: Embedding `task-2/participant` into its lexical child workspace should be rejected or explicitly warn that recursive reach will contain the starting workspace again through the ancestor's subtree.
- Actual: The embed succeeded. Recursive `show` terminated safely and deduplicated names, but expanded the workspace to 36 Contexts and 310 Memories through a topology that is difficult to predict from the success receipt.
- Workaround: Avoid embedding a lexical ancestor; embed only the required source categories.
- Severity: Medium modeling/usability risk; no infinite traversal or duplicate output was observed.
- Reproduction: Observed once, then verified once by recursive `show`.

## T2-CHUNK-02 — Clause chunking turns actionable policies into dependent fragments

- Expected: Chunks intended to become independent Memories remain independently actionable, or the operation preserves a typed relationship that downstream quality checks understand as one compound rule.
- Actual: Repeated clause chunks stored fragments such as `provenances.` and semicolon-ended partial rules as separate Memories. Early ambiguity runs returned 0/7 and 0/10; after five chunk attempts, the final scan flagged 11/15 direct Memories, mostly these fragments, and needed more than 30 seconds. The operation therefore created much of the cleanup workload it was meant to reduce.
- Workaround: Keep conditional policies whole, or immediately run `find-ambiguities` and manually merge/rewrite dependent chunks. The receipt's missing UIDs makes this workaround slower.
- Severity: High user-level workflow defect; meaning remains inferable in the combined frame but is unsafe when fragments are reused independently.
- Reproduction: Fragment creation occurred in 5/5 chunk attempts; downstream ambiguity impact was confirmed in the final scan.

## T2-GRANT-TRANSFER-01 — EXPORT-authorized grant Memories cannot be copied or referenced

- Expected: A readable granted Memory with effective EXPORT authority can be transferred into a local Context through an operation that preserves the appropriate copy or snapshot-reference semantics, subject to the documented target boundary.
- Actual: `copy` of advisor2/budget Memory `d614b55d` and `reference` of advisor1/scope Memory `1db5fcd6` both failed with `Context ... does not exist locally`, even though both source grants advertised READ + EMBED + DERIVE + COMBINE + EXPORT. The error treats authorization as locality absence and offers no grant-aware route.
- Workaround: Read the granted source, author a local synthesis with explicit provenance text, and retain the source UID in the audit ledger. This loses first-class transfer linkage.
- Severity: High for provenance-preserving co-advisor synthesis.
- Reproduction: Reproduced twice across two transfer commands, two advisor grants, and two source categories.

## T2-QUERY-TARGET-01 — Ordinary Query answered from prior local workspace instead of requested grant targets

- Expected: Repeated explicit `--context task-2/advisor1/budget --context task-2/advisor2/budget` freezes those two budget Contexts as the source frame, and every citation comes from them.
- Actual: The command exited successfully but cited five local workspace synthesis Memories and no requested budget Memory. This was more dangerous than a failure because the answer sounded plausible until the References were audited.
- Workaround: Audit every Reference block; use `search`/`compare` on the exact grant categories first, then query the explicitly attached recursive workspace and verify its citations.
- Severity: P1 candidate / High source-integrity defect.
- Reproduction: Observed once in the five-query matrix. Query-only exact-host success, wrong-host rejection, and recursive workspace success were controls, but the repeated ordinary grant-target route was not rerun beyond its allocated attempt.

## T2-SEARCH-DRIFT-01 — Semantic fallback silently changed the recruitment question and returned one advisor only

- Expected: A two-target search either returns relevant evidence from the requested sources or clearly separates an empty exact-query result from an optional broader-query suggestion.
- Actual: Search said there were no matches, automatically broadened `participant target exact number versus justified range` to `study participant sampling and scope`, and returned only two advisor1 items. The output was labeled `RELATED`, but accepting it without source auditing would bias the synthesis.
- Workaround: Move to the correct methods categories and use explicit exact/range wording; the later search then returned three advisor1 and seven advisor2 policies.
- Severity: Medium; visible label prevents silent factual substitution but adds recovery work and can skew attention.
- Reproduction: One drift case with a successful corrected-target control in round 4.

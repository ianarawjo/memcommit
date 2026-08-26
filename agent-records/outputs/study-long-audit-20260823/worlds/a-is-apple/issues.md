# a-is-apple phase-core issues

## AIA-CONTEXTS-01 — World orientation requires scanning the entire shared Profile

- Expected: Narrow inventory to `audit/a-is-apple` while retaining local/grant annotations.
- Actual: `contexts` printed roughly 128 lines for the complete Profile; later captures truncated the middle while the relevant six world Contexts occupied only the first few rows.
- Workaround: Search visually for the prefix, then use explicit Context operands everywhere else.
- Severity: Medium repeated-navigation cost.
- Reproduction: 5/5 rounds.

## AIA-LIST-REPEAT-01 — Recursive list visually repeats the same source through lexical and embed routes

- Expected: A recursive whole-world inventory indicates multiple reach paths without making the user reread identical Memories.
- Actual: The final list rendered `source` once as a lexical descendant and again beneath `working` as VIA EMBED; archive and comparisons were similarly repeated. The semantic scanner deduplicated them, but the list presentation did not.
- Workaround: Use exact `list`/`show` for each store or recursive `show` from `working`, which presents each reached Context once.
- Severity: Medium information-overload and reread cost.
- Reproduction: Observed in the final recursive list after three embeds; earlier recursive list before embeds was the control.

## AIA-CHUNK-01 — Successful chunk receipts omit every created UID

- Expected: The mutating receipt names each new Memory so later edit/move/reference operations can consume it directly.
- Actual: All three successful multi-chunk attempts reported only a count. Locating outputs required a later list/find and text matching. Two short-input controls correctly made no change.
- Workaround: Immediately list the exact Context and identify new fragments by content and placement.
- Severity: Medium output-reuse cost.
- Reproduction: 3/3 successful multi-chunk attempts; 2 no-split controls.

## AIA-CHUNK-02 — Clause chunks become context-dependent Memories

- Expected: Each created Memory is independently meaningful or carries a typed relationship to its neighboring chunks.
- Actual: Chunking produced fragments such as `retain the source UID for provenance.`, `chosen word.`, and `unresolved alternatives stay in comparisons.` Ambiguity analysis repeatedly flagged these because antecedents, exact UID, confirmation state, or alternative set were missing.
- Workaround: Keep the complete policy in `working`, then repair fragments with `edit` or avoid clause chunking for compact mappings.
- Severity: High because a curation operation creates downstream ambiguity and manual repair work.
- Reproduction: Dependent fragments appeared in 3/3 successful multi-chunk attempts; later ambiguity runs flagged them in rounds 2, 4, and 5.

## AIA-AMBIG-DECODE-01 — One ambiguity run fails after a long provider call

- Expected: The operation returns a validated ambiguity report or a stable empty report.
- Actual: Round 3 spent about 22 seconds and then failed with `Codex find_ambiguities returned a question for NONE.` No usable partial report was published.
- Workaround: Retry only after preserving the frozen Source frame; subsequent rounds succeeded, though the state had continued to change under the interleaved audit.
- Severity: High reliability/recovery cost for provider-backed review.
- Reproduction: 1/5 attempts; four successful controls show provider-output sensitivity rather than a deterministic local error.

## AIA-COMPARE-ASSOCIATION-01 — Compare attaches one mapping's provenance phrase to another mapping

- Expected: Relations remain adjacent to the exact Memory members that support them.
- Actual: The root-versus-source comparison correctly found b→boat versus b→banana, but then described banana as the preferred mapping copied from the original statement. That provenance phrase belonged to the neighboring a→apple fragments, not banana.
- Workaround: Audit the source Memories with exact `show`/`find`; do not materialize Compare prose without verifying each association.
- Severity: High semantic provenance defect because the concise report sounds plausible.
- Reproduction: Observed once. Later category comparisons with cleaner frames were accurate controls.

## AIA-SUMMARY-LANGUAGE-01 — Plain summary switches languages without a request

- Expected: English commands over English Memories produce an English summary unless language is explicitly requested or configured.
- Actual: Round 4 `summarize audit/a-is-apple/working --recursive --plain` returned Korean, forcing a language-context switch. The other four summaries were English.
- Workaround: Rerun with an explicit language instruction where supported, or use the English direct source summary.
- Severity: Medium usability and downstream-copy cost.
- Reproduction: 1/5 attempts with four English controls.

## AIA-EMBED-CYCLE-01 — Working accepts an embed of its lexical ancestor

- Expected: Embedding `audit/a-is-apple` into child `working` is rejected or warns that recursive reach contains the starting Context through the ancestor's subtree.
- Actual: The command succeeded after working already embedded source, archive, and comparisons. Existing recursive readers deduplicated traversal, but the receipt did not explain the cyclic topology.
- Workaround: Embed only the three required peer stores and avoid the ancestor edge.
- Severity: Medium topology/state-comprehension risk; no infinite traversal observed.
- Reproduction: One accepted ancestor embed; self-embed rejection in round 1 was a safety control.

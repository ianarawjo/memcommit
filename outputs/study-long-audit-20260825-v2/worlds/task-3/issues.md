# task-3 core audit v2 issues

No external healthcare transmission was executed. Candidate material and audit records remained in lane-local scratch. The outcome is a genuine user decision gate, not a completed disclosure.

## T3V2-CONTEXTS-OVERLOAD — Profile-wide Context discovery has no task-root narrowing

- Classification: **usability / information overload**
- Severity: **P2 / medium**
- Regression status: confirmed open from T3-CONTEXTS-OVERLOAD
- Reproduction: Yes — 5/5 interleaved attempts emitted the same whole-Profile catalog.
- Expected: A person working on task-3 can narrow discovery to its local and granted hierarchy while retaining current, ownership, Grant, and capability annotations.
- Actual: Each of five `contexts` attempts printed the identical 113-line, 7,624-byte Profile catalog. The first task-3 row begins only after 61 unrelated rows; the useful task-3 SHARE, QUERY, and READ/EXPORT Grant rows are at the end.
- Workaround: Scan once for the `task-3` prefix, then carry exact canonical names into later commands.
- Evidence: sequence 1 (`raw/core/001-contexts-a1.txt`), sequence 22 (`raw/core/022-contexts-a2.txt`), sequence 43 (`raw/core/043-contexts-a3.txt`), sequence 64 (`raw/core/064-contexts-a4.txt`), sequence 85 (`raw/core/085-contexts-a5.txt`)

## T3V2-RECURSIVE-READ-OVERLOAD — Recursive List and Show expand the full embedded personal tree without a compact mode

- Classification: **usability / information overload**
- Severity: **P2 / medium**
- Regression status: newly isolated evidence
- Reproduction: Yes across two sibling operations: one recursive List and one recursive Show of the same accumulated root.
- Expected: Recursive inspection gives a compact hierarchy and counts first, with a bounded way to drill into effective items when an embedded tree contains hundreds of Memories.
- Actual: `list task-3/local --recursive` emitted 904 lines / 68,257 bytes. `show task-3/local --recursive` reported 48 Contexts and 406 Memories, then emitted 752 lines / 62,365 bytes. The complete embedded personal history buried the few locally staged candidates and generated chunk UIDs.
- Workaround: Use `--direct`, inspect one exact child at a time, and carry UIDs from narrow receipts. There is no compact recursive summary switch in these attempts.
- Evidence: sequence 44 (`raw/core/044-list-a3.txt`), sequence 45 (`raw/core/045-show-a3.txt`)

## T3V2-SEARCH-DISPOSITION-GAP — Semantic relevance does not produce a safe disclosure disposition

- Classification: **semantic safety / review friction**
- Severity: **P2 / medium-high**
- Regression status: confirmed open from T3-SEARCH-CURATION
- Reproduction: Yes across three materially different semantic searches: broad personal, multi-root, and late safety-worded fallback.
- Expected: A privacy-sensitive candidate workflow keeps relevance, currency, third-party status, necessity, and approval visibly separate and makes multi-root coverage explicit.
- Actual: The broad personal search ranked a younger brother's transport preference beside medication and accessibility candidates. A two-root top-5 search returned only privacy policy Memories without saying the personal root contributed zero results. The final safety-worded search found no exact results, broadened the query, and returned stale medication evidence and unapproved drafts; it did clearly label them RELATED and warned that they may not satisfy the original query.
- Workaround: Search candidate and policy roots independently, reconcile exact Memories against currency/privacy/approval rules, and never treat ranking or RELATED fallback as an include decision.
- Evidence: sequence 26 (`raw/core/026-search-a2.txt`), sequence 47 (`raw/core/047-search-a3.txt`), sequence 89 (`raw/core/089-search-a5.txt`)

## T3V2-SUMMARY-CURATION — Narrative summary blends facts with different disclosure dispositions

- Classification: **semantic safety / privacy review**
- Severity: **P2 / medium-high**
- Regression status: confirmed open from T3-SUMMARY-CURATION
- Reproduction: One current-campaign privacy-sensitive month summary, consistent with the prior campaign's same behavior.
- Expected: A summary used during disclosure review keeps candidate personal facts, third-party facts, uncertainty, and approval state separately inspectable.
- Actual: The 2024/03 summary placed a historical medication instruction, clinic-standing/back discomfort, and the younger brother's advance-notice transport preference in one fluent paragraph. It noted medication currency uncertainty but did not mark the brother detail as a separately excluded third-party fact or emit include/exclude/verify dispositions.
- Workaround: Use summaries only for orientation, then return to exact Memories, quality findings, and explicit user review before materializing any outbound packet.
- Evidence: sequence 28 (`raw/core/028-summarize-a2.txt`)

## T3V2-CHUNK-SAFETY-FRAME — Clause Chunk splits a not-approved safety frame into independently retrievable facts

- Classification: **functional / semantic safety**
- Severity: **P1 / high**
- Regression status: confirmed open from T3-CHUNK-SEMANTICS
- Reproduction: One isolated destructive split, independently verified by Find Ambiguities and recursive List; no second unsafe split was performed.
- Expected: Chunking a disclosure draft preserves the relationship between its status, candidate fact, verification conditions, and approval boundary, or refuses a strategy that would detach them.
- Actual: One `DRAFT ONLY` medication candidate became three ordinary Memories: `DRAFT ONLY:`, `medication timing is a candidate;`, and a separate verification clause. Find Ambiguities then flagged the two substantive fragments as underspecified. The local review Context can now retrieve the medication claim without its not-approved marker.
- Workaround: Do not clause-chunk safety-gated disclosures. Keep status, fact, currency conditions, and approval in one Memory or use a typed compound structure.
- Evidence: sequence 36 (`raw/core/036-chunk-a2.txt`), sequence 40 (`raw/core/040-find-ambiguities-a2.txt`), sequence 44 (`raw/core/044-list-a3.txt`)

## T3V2-CHUNK-UID-OMISSION — Successful multi-Chunk receipt omits created Memory UIDs

- Classification: **functional / output reuse**
- Severity: **P2 / medium**
- Regression status: confirmed open from T3-CHUNK-TRACEABILITY
- Reproduction: One actual three-chunk mutation plus a later owner List that was required to recover all created UIDs.
- Expected: A successful split prints every created UID so Show, Edit, Move, Reference, quality checks, and audit records can consume the result directly.
- Actual: The receipt previewed three fragments and ended with `Done — 3 memories added`, but printed no created UID. Recursive List was needed to discover 26a4a267, eebb79a4, and d0f1069a.
- Workaround: Run List on the exact owner and manually match generated text to the new UIDs.
- Evidence: sequence 36 (`raw/core/036-chunk-a2.txt`), sequence 44 (`raw/core/044-list-a3.txt`)

## T3V2-COMPARE-SAME-CONTEXT-MEMORIES — Two documented direct-Memory endpoints cannot be compared when they share an owner Context

- Classification: **functional / operand contract**
- Severity: **P2 / medium**
- Regression status: new finding
- Reproduction: One exact same-owner/two-Memory attempt; deterministic application validation rejected it before provider work.
- Expected: The documented auto-typed Memory endpoint form compares two distinct Memories and uses their neighbors only as non-actionable context, including when both direct Memories share an owner.
- Actual: Two distinct qualified Memory endpoints, 18d58666 and e6023aed in 2024/03, were both recognized but the command failed before analysis with `Compare requires two distinct Contexts.` No state changed.
- Workaround: Compare the whole owner Context to another Context, or copy one Memory into a separate local scratch Context before comparison; neither is equivalent to the requested evidence-level comparison.
- Evidence: sequence 58 (`raw/core/058-compare-a3.txt`)

## T3V2-RECURSIVE-QUALITY-OVERLOAD — Recursive quality reports enumerate every empty child and semantic redundancy remains slow

- Classification: **usability / latency and report density**
- Severity: **P2 / medium**
- Regression status: confirmed open but materially faster than T3-RECURSIVE-OVERLOAD
- Reproduction: Yes across recursive exact-duplicate and semantic-redundancy sibling operations on the guardrail tree.
- Expected: Recursive quality checks foreground findings and summarize empty child frames, with drill-down evidence and bounded progress for semantic work.
- Actual: Recursive exact duplicate analysis printed 11 empty Context sections for zero groups. Recursive redundancy analysis checked 81 Memories in 11 frames, took 44.31 seconds, found zero groups, and printed all 11 empty sections. This is improved from the prior campaign's 176-second 46-Context example but remains expensive and noisy.
- Workaround: Use a broad literal/semantic retrieval pass to identify a likely child, then run quality analysis on that exact child; use JSON evidence only where a finding is expected.
- Evidence: sequence 59 (`raw/core/059-find-duplicates-a3.txt`), sequence 81 (`raw/core/081-find-redundancies-a4.txt`)

## T3V2-GRANT-EMBED-SEMANTIC-DEAD-END — A readable granted Embed blocks recursive semantic work through its local owner

- Classification: **workflow composition / authorization usability**
- Severity: **P2 / medium-high**
- Regression status: new finding; failure is correctly fail-closed
- Reproduction: Yes across two semantic consumers after one successful granted Embed: recursive Compare and recursive Summarize both failed closed.
- Expected: After a readable public Context is intentionally embedded, recursive semantic operations either skip the Embed with a visible reason, expose independent Embed traversal, or accept the same granted Source through an explicit authority-bearing peer selection.
- Actual: Embedding the READ+EMBED+DERIVE public guidance succeeded. A recursive Compare then explicitly selected that same public guidance as its peer, yet failed because the local reference frame encountered the granted Embed through its local owner. Final recursive Summarize of `task-3/local` failed for the same reason. Both failures occurred before provider connection/publication and clearly explained the authority boundary.
- Workaround: Use direct local scope, summarize/compare individual local children, and select the granted Source separately. Once embedded, there is no observed recursive-local scope that includes lexical descendants while excluding only granted Embeds for these commands.
- Evidence: sequence 74 (`raw/core/074-embed-a4.txt`), sequence 79 (`raw/core/079-compare-a4.txt`), sequence 91 (`raw/core/091-summarize-a5.txt`)

## T3V2-FIT-OPAQUE — Positive Fit receipts expose no support, exclusions, or next action

- Classification: **usability / decision explainability**
- Severity: **P2 / medium-high**
- Regression status: confirmed open from T3-FIT-OPAQUE
- Reproduction: Yes — 4/4 successful Fit attempts across Context, direct-Memory, and granted-Source methods returned only YES plus targets.
- Expected: A positive Fit result identifies the propositions/evidence that jointly fit, what was excluded or uncertain, and why the result is not approval for external disclosure.
- Actual: All four successful Context/Memory/granted-source attempts printed only `FIT · YES` and target labels. They exposed no receipt UID, source-linked rationale, mismatches, uncertainty, excluded items, or next review action. The empty direct-root attempt failed clearly and safely.
- Workaround: Use Compare, Query References, exact Show, and ambiguity/conflict analysis to reconstruct evidence. Treat Fit YES only as joint consistency, never disclosure approval.
- Evidence: sequence 42 (`raw/core/042-fit-a2.txt`), sequence 63 (`raw/core/063-fit-a3.txt`), sequence 84 (`raw/core/084-fit-a4.txt`), sequence 105 (`raw/core/105-fit-a5.txt`)

## T3V2-JSON-ZERO-SILENCE — Structured evidence modes emit an empty stream for a successful zero-finding result

- Classification: **machine-consumption / observability**
- Severity: **P3 / low-medium**
- Regression status: new finding
- Reproduction: Yes — three zero-finding structured attempts across two operations emitted nothing; a nonzero redundancy attempt emitted canonical JSON.
- Expected: A machine-readable zero-finding result emits a stable empty-result record or summary so callers can distinguish successful zero from accidentally lost output without relying only on process status.
- Actual: `find-conflicts --handoff-json` twice and `find-redundancies --evidence-json` once exited 0 with zero stdout and stderr when no findings existed. The same redundancy mode emitted canonical JSON when one finding existed, confirming the silent stream is the zero-result representation.
- Workaround: Capture the exit code and run the human-readable form when an explicit zero receipt is required.
- Evidence: sequence 62 (`raw/core/062-find-conflicts-a3.txt`), sequence 102 (`raw/core/102-find-redundancies-a5.txt`), sequence 104 (`raw/core/104-find-conflicts-a5.txt`)

## Regression checks that passed

- **T3-QUERY-TARGETING resolved in this snapshot:** four exact QUERY-only routes (sequences 6, 27, 69, and 90) returned endpoint-specific scope and capability answers; none labeled or quoted `task-3/local/personal-memory`. Ordinary multi-root Query at sequence 48 separately returned source-linked References.
- **T3-GRANT-SELECTIVE-TRANSFER resolved in this snapshot:** selective granted Memory Reference (sequence 73) and Copy (sequence 93) both succeeded and preserved the public Source owner. Whole-Context Embed also succeeded at sequence 74.
- **T3-AMBIGUITY-PROVIDER did not reproduce:** all five ambiguity attempts succeeded, including the 25-Memory granted frame and 14-Memory final audit frame.
- Parser and safe-boundary checks behaved correctly: invalid singular Chunk, empty direct-root Fit, and same-owner Move all failed without changing the task-3 Context tree; valid later routes recovered.

## Safe world outcome

The evidence supports only local candidate review. Potentially useful categories are explanation-format preferences and an accommodation/waiting experience, but both need currentness, necessity, and exact-item review. Historical medication timing is stale and lacks medication identity/current prescription. Relatives' contact, transport preferences, private reasons, and unrelated family/restaurant history remain excluded. Exact recipient/authority, purpose, items, channel, retention terms, and explicit user approval are still missing, so no Share or external transfer was attempted.

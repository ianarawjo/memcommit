# Task-1 transform issues

Transform completed 24 operations × 5 materially different routes with one cumulative no-reset Store.

## T1-V2-ATOMIZE-WHOLE-FRAME-UNCERTAIN — Whole-frame Atomize cannot reach semantic chunk normal form

- Severity: medium
- Classification: provider-schema-infrastructure/reliability
- Expected: Whole direct construction frames should either produce complete reviewable Atomize sessions or identify a bounded input-size/schema limit before provider work.
- Actual: The 19-Memory facility frame ran for 51.07 s and returned 14 UNCERTAIN dispositions; the 15-Memory parking frame ran for 42.54 s and returned one UNCERTAIN disposition. Both rejected the whole result with no Context publication, while three focused-Memory routes succeeded.
- Workaround: Use exact Memory Atomize routes and review each source-bound result; do not treat focused success as whole-frame coverage.
- Evidence: T1-V2-TRANSFORM-001, T1-V2-TRANSFORM-073

## T1-V2-AUDIT-CROSS-FRAME-LATENCY — Cross-frame Audit approaches or exceeds the bounded call timeout

- Severity: medium
- Classification: provider-infrastructure/performance
- Expected: A complete saved cross-Context Audit should finish within the declared 300-second bounded-call window or fail early with a size/cost diagnostic.
- Actual: Building-access against route-changes reached the 300-second harness timeout with no completed artifact; temporary-parking against building-access completed only after 252.01 s. Single-frame Audits completed in 18.29–30.38 s.
- Workaround: Run single-frame Audit snapshots and a separate Check Conformance call for the cross-area rule frame, preserving both receipts.
- Evidence: T1-V2-TRANSFORM-050, T1-V2-TRANSFORM-074

## T1-V2-IMPACT-AUDIT-ROUTE-GAP — Impact cannot consume a saved Audit session

- Severity: low
- Classification: operation-consistency/usability
- Expected: A saved read-only Audit artifact should have an operation-aware Impact route, consistent with other saved semantic analysis sessions.
- Actual: `impact audit --session deadbeef` was rejected by the command router with `No such command 'audit'`; the failure occurred at routing before artifact lookup, even though Audit is a saved session family and `review audit` exists.
- Workaround: Use `review audit --session … --snapshot` to inspect the immutable artifact; no Audit-specific Impact preview is available.
- Evidence: T1-V2-TRANSFORM-063

## T1-V2-RATIONALE-LANGUAGE-DRIFT — Rationale unexpectedly switches from English to Chinese

- Severity: medium
- Classification: provider-presentation/usability
- Expected: Rationale prose should follow the English source and surrounding CLI language unless a target language is explicitly requested.
- Actual: The first facility Rationale rendered its entire provenance explanation in Chinese. The four otherwise equivalent construction Rationale routes rendered English.
- Workaround: Use Trace for language-stable lineage facts, or rerun Rationale and manually verify its prose against the typed provenance events.
- Evidence: T1-V2-TRANSFORM-018

## T1-V2-ELABORATE-UNSUPPORTED-DETAILS — Bounded Elaborate invents venue verification procedures

- Severity: high
- Classification: semantic-integrity/unsupported-generation
- Expected: The inline rule requiring only verified venues, dates, and reservation status should not produce concrete operational channels, active/pending booking states, or loading-entrance details absent from the verified construction Source.
- Actual: Elaborate created three UNVERIFIED/BEST_EFFORT Memories that introduced an auditorium reservation channel, active and pending booking states, and a separate loading entrance for equipment. These details were not in the verified event-relocation Memories.
- Workaround: Keep Elaborate output in checkpointed scratch, treat UNVERIFIED as non-publishable, and Revert unless every generated detail can be independently grounded.
- Evidence: T1-V2-TRANSFORM-033

## T1-V2-AUDIT-HARNESS-SESSION-PARSE — Audit evidence runner did not recover bracketed session IDs

- Severity: low
- Classification: audit-harness-infrastructure
- Expected: The audit harness should recover the saved `SESSION [uid]` token so the later counted Review can consume that exact artifact.
- Actual: The world-local runner recognized only a printed `mem review audit --session` command, not Audit's actual `SESSION [uid]` header, so Review attempts 1 and 4 used the sentinel `deadbeef` and failed. The underlying Audit artifacts were successfully saved.
- Workaround: Read the bracketed SESSION UID from raw Audit output; do not attribute these Review failures to the product.
- Evidence: T1-V2-TRANSFORM-002, T1-V2-TRANSFORM-020, T1-V2-TRANSFORM-074, T1-V2-TRANSFORM-092

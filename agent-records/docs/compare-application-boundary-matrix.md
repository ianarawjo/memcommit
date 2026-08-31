# Compare application boundary matrix

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Lightweight Summary implementation ownership

The default transient Compare path is owned by
`memcommit.application.operations.search_explain.synthesize.compare.compare_summary`, `.compare_rules`,
`.provider_contract`, and `.application`. The former flat
`memcommit.comparison_summary*` module paths are identity-preserving
compatibility aliases so import order, monkeypatches, and pre-relocation pickle
references resolve to the same canonical modules and classes. New production
code imports the operation package directly.

This ownership move does not combine the transient paragraph with the deep
ledger lifecycle below. The exhaustive relation model, evidence, provider,
execution, and repositories live in
`application.capabilities.memory_issue_analysis.peer_relations`; Compare's
`operations.compare.sessions` owns Run/Open/Refresh request semantics over that
capability. Plain-text rendering remains interface-owned and is not imported
by either application boundary.

## Operation shape

| Property | Contract |
| --- | --- |
| Source roles | ordered equal-authority `REFERENCE A` and `PEER B` |
| Scope | exact Context, readable lexical descendants, or one stored exact direct-Memory UID per side |
| Provider strategy | one exhaustive whole-ledger turn; no hidden batching or truncation |
| Context effect | none |
| Durable metadata effect | at most one CAS replacement of the ordered pair's latest analysis slot |
| Checkpoint / Undo | not applicable; no Context mutation |
| Saved lifecycle | Run, exact Open, version-bound Refresh |

## Entry-point matrix

| Use case | Typed owner | Python | Agent | CLI / TUI |
| --- | --- | --- | --- | --- |
| Default transient summary | `operations.compare.application.run_comparison_summary` | not exposed as the deep public API | not exposed as the deep agent API | default explicit endpoints or endpoint setup |
| Run or reuse | `memory_issue_analysis.peer_relations.execution.ensure_comparison_analysis` | `compare_contexts` | `kind=run` | explicit endpoints or endpoint setup |
| Open exact saved analysis | `operations.compare.sessions.open_comparison_session` | `open_comparison` | `kind=open` | saved-session picker |
| Refresh reviewed analysis | `prepare_comparison_refresh` plus production execution | `refresh_comparison(expected_version=...)` | `kind=refresh` | explicit `--refresh` freezes the current slot at command start |

## Cache matrix

| Candidate | Durable | Provider | Result origin | Boundary |
| --- | --- | --- | --- | --- |
| exact current saved analysis | yes | no | `SAVED_REUSE` | exact frame, scope, source digest, and ruleset |
| installed exact hidden analysis | materialized on use | no | `EXACT_PREWARM` | authority and complete current frames precede lookup |
| ancestor-equivalent hidden analysis | materialized on use | no | recorded equivalent origin | operation-owned equivalence proof |
| safe descendant-subset projection | no | no | `PROJECTED` | complete projected relation coverage; cannot Open |
| live miss | according to local/Grant retention | one complete turn | `LIVE` | strict decoder and post-provider source revalidation |
| Refresh | according to current retention | one complete turn | `LIVE` | bypasses reuse by explicit contract |

## Failure ordering

1. validate action shape, locators, scope combinations, analysis UID, and opaque
   version;
2. resolve READ access and COMBINE authority for both ordered sources;
3. freeze complete source projections and Grant bindings;
4. for Refresh, compare the reviewed version before cache or provider work;
5. execute exact reuse, hidden lookup/projection, or the bounded provider turn;
6. revalidate sources, Grants, retention authority, and the prior slot;
7. publish one complete artifact only when both prior UID and canonical digest
   match.

No failure may publish a partial relation ledger or mutate a source Context.

The frozen projection includes ordinary local content and effectively
READ-granted content only. A process-local `authority-grant` query row marks a
narrower QUERY authorization route for navigation; it is not readable content
or a hierarchy edge, so Compare excludes it without opening the concealed
Context. An ordinary persisted `QueryContextRef` remains an explicit failure
because silently omitting stored source structure would change the comparison
frame.

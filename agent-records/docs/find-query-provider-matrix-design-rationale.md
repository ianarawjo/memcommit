# Search and Query provider-matrix design rationale

## Status

This note records a completed one-off provider-selection experiment. The
evaluation runner and its dedicated tests were retired from the distributed
package on 2026-08-27 after the matrix result and subsequent policy decisions
had been retained. The final executable snapshot is recoverable from commit
`4ff5119bc`; the runner was originally introduced in commit `bb7ddaafa`.

The completed 54-call ledger and its readable summary remain under
`agent-records/outputs/find-query-latency/`. Retiring the runner does not change
the Task 3 fixtures, active Search or Query provider policy, production prompt
contracts, or their ordinary tests.

## Problem

Forget's compact-corpus evidence made `gpt-5.6-sol` with no reasoning a useful
latency setting, but that result cannot be transferred to Search or Query without
operation-specific evidence. Search must satisfy a strict candidate-ID schema and
rank a 300-Memory corpus. Query instead produces a free-form answer from one
opaque 75-Memory source. Earlier Compare evidence also showed that a faster
reasoning setting can violate one operation's output contract even when another
operation accepts it.

## Frozen matrix

The evaluation crosses three subscription-backed Codex models
(`gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`) with `none`, `low`, and
`medium` reasoning. Each condition sees six English Task 3 cases once:

- Search has two historically observed study searches and one deliberately
  unsupported lookup.
- Query has one multi-fact synthesis, one narrow boundary question, and one
  request for details absent from the source.

The 54 calls are sequential. Their order is rotated by case so one condition is
not always first, but the run does not introduce concurrent provider load as a
new variable. One repetition is a smoke matrix, not a variance estimate; any
deployment recommendation should be confirmed with repeated runs when the
latency difference is small.

## Production-contract reuse

The historical runner in `memcommit.eval.find_query_latency` loaded only
versioned study fixtures and built an in-memory Context hierarchy. It reused
the production Search prompt, JSON schema, candidate collector, decoder, and
ranker. It also reused the production Query prompt over the same
newline-separated source projection. Search used exactly one provider primitive
in this campaign; fixture growth that would have triggered staged execution
failed the cell instead of silently changing the experimental unit.

No profile, current Context, provider preference, session, or durable Memory
was read or changed. Every Codex completion was an isolated ephemeral process.
The campaign output retains raw completions but omits full prompts because the
prompt can be reconstructed from the fixture digest and case definition.

## Quality interpretation

The two observed Search result lists and the smaller human-checked subsets are
historical references, not a gold relevance judgment. Metrics are therefore
named `historical_result_recall`, `historical_result_precision`, and
`study_selected_recall`. The unsupported Search case separately checks that the
primary tier stays empty; a clearly labelled related fallback remains valid.

Query scoring records whether transparent regular-expression probes find each
required source concept and whether an unsupported answer invents an exact day
count. `concept_recall` is a deterministic diagnostic over paraphrased text,
not an absolute semantic score. Raw answers and per-concept matches remain in
the ledger so a person can audit false negatives or superficially matched text.
The first smoke run exposed false negatives for ordinary phrases such as “does
not specify an exact retention period.” Version 2 broadened only those scoring
probes after auditing the retained answers; it did not change prompts, cases,
provider outputs, or timing measurements.

## Atomicity and limitations

The JSON ledger was replaced atomically after every cell, and `--resume`
skipped only cells already present under the same campaign fingerprint.
Provider errors and invalid Search structures were retained without discarding
later cells. The ledger reports connection, provider, validation, and total
wall time separately.

The campaign is English-only, uses one public synthetic fixture family, and
does not measure TUI rendering, user review time, multi-call staged Search, or
provider-service variance across repeated days. A condition should not be
selected from latency alone: structure validity, unsupported-answer behavior,
and the auditable quality diagnostics remain hard gates.

## Original selected operation policy

After reviewing the smoke matrix, the project selected `gpt-5.6-terra` with
`low` reasoning for both Search and Query. Terra/low led the two Search reference
metrics while remaining materially faster than Sol/medium. Query's fastest
full-coverage condition was Terra/none, but Terra/low also retained complete
audited concept coverage and the unsupported-answer boundary. Using one shared
Terra/low policy was selected to avoid an operation-dependent reasoning switch
for a small measured latency difference in this single-repetition run.

That original pin applied to the Search command family, ordinary Query, and
query-only routes whose authorized provider was Codex ChatGPT.

## Query one-shot supersession

The original Query comparison measured a different execution unit: a free-form
answer over one already assembled source projection. Ordinary Query later used
two isolated provider turns—a Terra/low top-k rerank followed by Terra/low
answer synthesis—which could reduce a 378-item frozen corpus to a single
aggregate artifact before the answer model saw it. The earlier matrix therefore
does not justify retaining Terra/low after removing that ranker.

The whole-corpus ordinary Query decision documented in
`ordinary-query-one-shot-design-rationale.md` supersedes the Query half of this
selection. Search keeps its independent provider policy and `TOP_K_RERANK`.
Codex-backed Query now uses Sol/none for its one-shot answer-and-alias contract.
This does not change the global semantic-provider preference, Forget's
independent policy, historical evaluation conditions, or a query-only Grant
explicitly routed to another allowlisted provider. Shared timeout and
subscription-authentication checks remain authoritative.

## Production owner and compatibility

`memcommit.providers.operation_connections` is the single production owner of
the shared Search, Query, and Help connection adapters. The neutral module name
reflects that the owner is not a Search/Query command helper. Search and Query
commands and public clients import it directly; the former Search command
provider-policy module is removed rather than retained as an inverse facade.
Optional model/reasoning/timeout arguments exist only to inject one
already-frozen non-secret client snapshot; no connector mutates user
configuration.

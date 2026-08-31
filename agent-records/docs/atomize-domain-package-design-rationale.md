# Atomize domain package design rationale

## 2026-08-29 responsibility revision

The structural `domain` package described below remains current. The later
Grounding package description is retained as schema-ownership history only:
its model package still decodes and validates persisted records, but the
provider, runtime, application, Meld adapter, console, Python, and agent routes
were removed. New Atomize execution cannot create or consume a Grounding turn.
See
[`atomize-read-only-findings-design-rationale.md`](atomize-read-only-findings-design-rationale.md)
for the current operation boundary.

## Motivation

The Atomize domain implementation had grown to 3,241 lines in one
`domain.py`. It jointly owned domain values, the one-shot semantic-provider
contract, analysis-session persistence, candidate orchestration, and structural
application. Those responsibilities changed for different reasons and made a
focused edit require understanding the entire operation kernel.

## Selected boundary

`memcommit.application.operations.atomize.domain` is now a package with five
implementation modules:

- `model.py` owns operation-neutral values, rules, report records, and the
  provider protocol.
- `provider_contract.py` owns calibration, prompt and schema construction,
  semantic-execution preflight, and fail-closed provider decoding.
- `analysis.py` owns candidate selection, linting, and non-mutating analysis
  orchestration.
- `session.py` owns declared-frame provenance, durable schemas, legacy loading,
  digests, and stale-analysis detection.
- `structural_apply.py` owns validated in-memory replacement and trace/normal-
  form evidence records.

The package `__init__.py` remains a thin compatibility facade. Existing imports
from `memcommit.application.operations.atomize.domain` keep the same callable
and value surface while new implementation code can import its narrow owner.

## Historical conversational Grounding model boundary

Atomize Grounding is a separate durable dialogue contract rather than part of
the one-shot analysis model, but its former `grounding.py` had accumulated
1,908 lines of frozen inputs, provider-review records, user decisions, change
receipts, and aggregate validation. It is now a concept-owned package:

- `bindings.py` owns Context, analysis, workbench, and response bindings,
  canonical digests, strict parsing primitives, and the selected issue anchor;
- `review.py` owns direct and downstream outcomes, follow-up questions,
  proposals, cumulative assessments, dialogue turns, and user decisions;
- `changes.py` owns content-addressed change sets and post-transaction
  application receipts; and
- `session.py` owns lifecycle transitions, cross-record validation, accepted-
  proposal materialization, and application-state reconciliation.

The dependency direction remains `session -> changes -> review -> bindings` for
legacy record decoding. `memcommit.application.operations.atomize.grounding`
is the schema facade used by Store history and restoration. The former Context
mutation owner, `grounding_runtime.py`, no longer exists; no active caller may
prepare or apply a new Grounding change set.

## Invariants

- The split changes code ownership, not Atomize semantics. Classification,
  child proposals, the overview, and the complete local quality scan remain one
  bounded provider completion.
- Provider output remains fail-closed: complete candidate coverage, literal
  source grounding, kind-specific quality constraints, and durable round-trip
  validation are unchanged.
- Saved analysis schemas and ruleset versions remain readable and retain their
  original digest and provenance checks.
- Structural application still validates and allocates every result before the
  first Context mutation.
- The legacy facade preserves the module-level prompt-policy and input-limit
  override seams used by tests and controlled study execution.

## Alternatives and limitations

Keeping `domain.py` and extracting only helper functions would leave the
persistence and provider contracts coupled to one oversized owner. Splitting
classification, child generation, ambiguity, and conflict into separate
provider calls was rejected because it would change the complete-frame quality
contract and could publish internally inconsistent judgments. The facade still
has a broad public surface for compatibility; callers can migrate toward the
narrow modules gradually, after which obsolete re-exports may be removed in a
separately versioned change.

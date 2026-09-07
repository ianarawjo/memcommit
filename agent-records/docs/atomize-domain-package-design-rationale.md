# Atomize domain package design rationale

## 2026-09-06 unused response export removal

The response split initially preserved six private names through three package
facades: `response`, `provider_contract`, and `domain`. A repository search
found no consumer of those re-exports beyond the facades themselves. Analysis
already calls `entrypoint.parse_response`, and the section readers and example
loader import their field helpers directly. No test patches the six aliases;
they are also excluded from `domain.__all__`.

Remove `_parse_items`, `_exact_dict`, `_reject_duplicate_json_keys`,
`_short_string`, `_parse_overview`, and `_parse_quality_issues` from all three
facades together. Keep `response/__init__.py` as a package description and
retain the actual implementations in their owning modules. Leaving aliases
at an upper level would preserve the same unused dependency chain.

Keeping or deprecating the aliases was rejected because no repository consumer
or supported external contract was identified. This deliberately stops
supporting direct imports of these private names from the facades; unknown
external callers must use the implementation modules. Other domain exports,
including the policy and limit override seams, are outside this cleanup.
Provider payloads, complete-response validation, and saved schemas are unchanged.

The review ran 113 focused analysis, application, review, result, workbench,
and semantic-policy tests both before removal and with all six exports removed
from the three facades in memory; both runs passed.

## 2026-09-05 response section reading split

After the first provider-contract split, `response.py` still contained 581
lines. Most of that code followed three actual fields of the provider response:
`overview`, `items`, and `quality_issues`. The whole-response reader was also
named `_parse_items`, obscuring that it decoded the envelope and assembled all
three sections in addition to validating individual Memory results.

`provider_contract/response/` now groups that code by the response sections:

- `entrypoint.py` owns `parse_response`: JSON decoding, exact envelope checking,
  and assembly of the three validated sections.
- `items.py` owns `parse_items`: complete candidate coverage, classifications,
  split children, literal source/frame evidence, and candidate-order output.
- `overview.py` owns the existing three overview-section readers.
- `quality_issues.py` owns the existing ambiguity/conflict validation, reading
  and issue construction, durable round-trip check, and deterministic ordering.
- `fields.py` owns duplicate-JSON-key rejection and basic field checks. Example
  loading imports the JSON helper from this narrow module.
- `__init__.py` marks the response package. Analysis imports the explicitly
  named entry point directly. The temporary compatibility aliases introduced
  during the split were removed after the consumer review recorded above.

Validation order remains items, overview, then quality issues. Nothing is
returned until all three succeed. Error messages, citation deduplication,
duplicate-candidate rejection, source grounding, and output ordering remain
unchanged. The provider still receives the same prompt/schema in one call,
and saved record formats are unchanged.

The section boundaries were chosen for reading, not to move semantic rules
between architectural layers. Shared domain validation and the quality issue
round-trip remain separate decisions. Ambiguity and conflict stay together
within the existing quality-issue reader; splitting every branch now would
make a single response section harder to follow.

## 2026-09-05 provider contract reading split

The 1,228-line `domain/provider_contract.py` is now a package at the same
import path. The purpose is to make the existing contract readable in smaller
pieces before considering changes to its design:

- `examples.py` loads authored examples, checks fixture/profile integrity, and
  filters cases by the active evidence mode. The name describes the actual
  data rather than suggesting an adaptive calibration process.
- `prompt.py` constructs the payload and prompt, including the existing
  one-shot budget check.
- `response_schema.py` describes the provider's structured response format.
- `response.py` initially grouped response parsing, validation, and domain
  projection; the subsequent section split above replaces it with `response/`.
- `__init__.py` retains the example, prompt, and schema exports. Response
  readers use only their implementation paths after the cleanup above.
  Analysis imports the narrow implementation modules directly.

In this first split, function names and bodies, prompt text, example selection, schema, error
messages, source grounding, output ordering, and the single provider call are
unchanged. The existing domain facade's prompt-policy and input-limit override
seams remain available. No saved schema or ruleset version changes.

This first split postponed moving execution policy out of prompt construction,
extracting shared semantic validators, renaming functions, and splitting the
response parser further. The response section revision above takes the next
reading step; execution-policy and semantic-validation changes remain deferred.

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
implementation owners (the provider contract is now the package above):

- `model.py` owns operation-neutral values, rules, report records, and the
  provider protocol.
- `provider_contract/` owns authored examples, prompt and schema construction,
  semantic-execution preflight, and fail-closed provider decoding.
- `analysis.py` owns candidate selection, linting, and non-mutating analysis
  orchestration.
- `session.py` owns declared-frame provenance, durable schemas, legacy loading,
  digests, and stale-analysis detection.
- `structural_apply.py` owns validated in-memory replacement and trace/normal-
  form evidence records.

The package `__init__.py` remains a thin compatibility facade for domain
values and operations. The six unused private response exports are removed as
recorded above; implementation code imports the narrow owner.

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
has a broad surface for domain values and operations. This cleanup removes only
the six private response exports after checking their consumers; the existence
of other re-exports does not establish a need to preserve unused names.

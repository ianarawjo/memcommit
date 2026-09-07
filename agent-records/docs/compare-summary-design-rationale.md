# Lightweight Compare summary design rationale

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Motivation

The original `mem compare` always constructed the same exhaustive relation
ledger needed by symmetric Meld. That contract assigns every frozen Memory
exactly once, synthesizes four reports, classifies N:M relations, and may
create review Issues. It is valuable preparation for reconciliation, but it is
too much work for the ordinary question “what do these two Contexts broadly
share and how do they differ?”

The perceived delay had two independent components. Recent local timing
evidence showed a small Codex/none provider turn taking roughly 21–50 seconds,
while one 195-second command retained the completed full-screen result for
about 145 additional seconds. Provider selection alone therefore could not
explain the visible command duration. The default semantic contract and the
result lifecycle both needed to become smaller.

## Two explicit execution contracts

Default `mem compare REFERENCE PEER` now produces one transient
`ComparisonSummary`:

- exactly one concise source-linked prose paragraph under a minimal
  `Compare · A ↔ B` / `COMPARISON` receipt;
- one dominant semantic relationship and, when needed, one decisive
  difference, condition, exception, or consequence;
- no relation objects, source assignments, Issues, Meld dispositions, or
  application proposal;
- no comparison-analysis file, session row, checkpoint, or Context mutation;
- one short terminal result that returns control immediately instead of
  opening a resident result workbench.

`mem compare REFERENCE PEER --ledger` remains the explicit deep route. It
constructs and saves the complete `ComparisonAnalysis` with exhaustive source
coverage and exact relation evidence. `--refresh` also retains that legacy
deep contract because it is defined as replacement of a reviewed saved
analysis. Symmetric Meld continues to obtain the same exhaustive basis through
the shared Compare execution boundary when its current basis is missing or
stale. Saved rows remain accessible through `mem compare --sessions` and
`mem review compare`.

This split keeps the ordinary operation analogous to Summarize or Rationale:
the provider answers the human reading task actually requested. Deep Compare
is no longer hidden behind the default spelling, while Meld loses none of the
coverage it requires.

## Implementation ownership

The transient contract has one canonical operation package:

- `operations.compare.compare_rules` owns the versioned compact-relation
  rules and checked-in fixture decoder;
- `operations.compare.compare_summary` owns the immutable bounded result;
- `operations.compare.provider_contract` owns prompt planning, schema, and
  strict decoding; and
- `operations.compare.application` owns COMBINE authorization,
  provider invocation, and post-call source revalidation.

The previous flat `comparison_summary*` paths are module-identity aliases for
import and pickle compatibility, not alternate implementations. The package
initializer performs no eager imports, so importing the operation namespace
does not construct a provider or assemble either Compare contract.

Plain-text rendering remains an interface concern. The ownership move does
not relocate the presenter into the operation package, and none of the four
canonical modules imports command or terminal code. It also deliberately
leaves the exhaustive model, provider, stores, execution, session lifecycle,
saved JSON, and Meld basis unchanged.

## Lightweight provider and evidence contract

The summary request freezes the same exact ordered Context frames and optional
Memory selectors as deep Compare. Provider aliases remain call-local and
Context names remain presentation-only. The strict output schema contains
only one `{text, source_ids}` paragraph. It has no field capable of carrying a
relation ledger or review Issue.

The single current ruleset enters each provider turn, with its exact plus
known-wrong cases when the prompt policy includes authored examples. They
calibrate the shapes observed in real
Study data: selected numeric conditions, one rule against many instances,
temporary overrides against a larger baseline, a general policy against its
domain specialization, and two tasks whose shared selection work leads toward
opposite governance outcomes. These examples are consumed production
calibration, not held-out evaluation evidence.

The paragraph must cite known frozen aliases from both peers and must cite
`PRIMARY` evidence from both sides. Neighboring `CONTEXT` rows may disambiguate
a selected Memory but cannot become another comparison topic. Evidence aliases
are decoded to immutable Memory UIDs before presentation, and the decoder
rejects any alias that leaks back into prose. This separation matters because
one actual 1-to-26 rule/instance run printed `[A1] [B1] ... [B26]`, while a
selected 1-to-1 run expanded into unrelated heading guidance from neighboring
Context rows.

The provider reads both complete frames but aims for roughly 45 words in one
or two sentences, with an 80-whitespace-word hard limit. It leads with the
dominant relation—equivalence, conditional alternatives, rule/instances,
override/baseline, general/specialized, shared core with one decisive delta,
or no material relation. Exact numbers remain attached to the condition that
makes them discriminating. Source-count asymmetry is expressed through these
semantic roles rather than treated as authority. The paragraph uses the
shared PRIMARY language, or the REFERENCE primary language when the sides
differ. The schema and decoder reject provider-authored line breaks, while
ordinary terminal wrapping remains presentation-only.

The summary declares `HIERARCHICAL_REDUCE` but does not claim a staged
reconciler. An over-budget pair fails before provider connection instead of
being silently partitioned or truncated. The exhaustive deep route retains
its independent whole-frame coverage contract and 900-second timeout floor.

## Authority and concurrency

The application authorizes `COMBINE` before connecting a provider and freezes
every granted binding. After inference, it resolves both local and granted
accesses again under the authority snapshot lock, reloads the exact requested
scope, and compares Context and Memory digests with the frozen input. A source
or Grant change suppresses the result. This post-call check matters because a
transient result has no artifact CAS write that could otherwise serve as a
publication boundary.

No summary is persisted, including when all sources permit retained analysis.
Retention authority is relevant only to the explicit ledger/Meld path.

## Alternatives considered

Keeping the exhaustive call and merely switching to a faster model was
rejected because it would still pay for a semantic product the default caller
did not request. Rendering a local summary from relation rows was rejected
because exhaustive relation generation remains the dominant work and a local
projection could make incomplete prose look independently validated. Caching
the lightweight summary was deferred: it would add lifecycle and provenance
cost before there is evidence that this intentionally small, read-only result
needs durable identity.

Running one semantic comparison per child or Memory was also rejected. Actual
pairwise month checks over the Study personal-memory tree took roughly 168
seconds across eighteen serial calls, recreating the latency this contract is
meant to remove. A future hierarchical result must use an explicit staged
strategy with operation-owned reconciliation and atomic publication; a UI
loop over independent provider calls is not a valid shortcut.

## Compatibility and limitations

The summary/ledger split keeps the deep saved-analysis lifecycle separate.
The default CLI does not create or refresh those artifacts. Automation that depended
on that implicit side effect must add `--ledger` (or `--refresh` when replacing
an exact reviewed slot).

The lightweight prompt still reads the complete bounded selected frames in one
turn. It reduces output obligations and review lifecycle, not input disclosure
or the need for a model to understand both peers. Future latency work may add
a validated hierarchical reconciler, but batching is not enabled by this
change.

The compact result is not an exhaustive coverage claim. A caller that needs
every Memory disposition, issue, or application-ready relation must use
`--ledger`. An empty direct frame still fails before provider connection rather
than producing prose about absence.

## Single current contract (2026-09-06)

The user explicitly removed the requirement to maintain comparison ruleset
revisions or read older comparison results in this unreleased prototype.
`ComparisonSummary` therefore carries no `ruleset_version`, and neither the
checked-in rule fixture nor the provider payload has a semantic version label.
The fixture still has one structural format and its named rules, examples,
word limit, source citations, and strict decoder are unchanged. There is no
replacement prompt hash, revision counter, or regeneration policy.

The module exports its error and result in their definition order, at the top
of the file; the rule module owns the rules without re-exporting a version
through the result model. The shared ledger's matching cleanup is recorded in
[Peer Relation Analysis](peer-relation-analysis-design-rationale.md#single-current-contract-2026-09-06).

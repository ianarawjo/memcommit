# Lightweight Compare summary design rationale

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

- exactly one concise source-linked prose paragraph with no authored line
  breaks, headings, labels, bullets, or category template;
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

## Lightweight provider and evidence contract

The summary request freezes the same exact ordered Context frames and optional
Memory selectors as deep Compare. Provider aliases remain call-local and
Context names remain presentation-only. The strict output schema contains
only one `{text, source_ids}` paragraph. It has no field capable of carrying a
relation ledger or review Issue.

The paragraph must cite known frozen aliases from both peers. Evidence aliases
are decoded to immutable Memory UIDs before presentation. The provider is
instructed to integrate salient common ground, differences, and side-specific
points naturally in under about 140 English words instead of mechanically
enumerating categories. The schema and decoder reject provider-authored line
breaks, while ordinary terminal wrapping remains presentation-only.

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

## Compatibility and limitations

Existing deep analysis JSON, saved-session reopening, public deep Compare API,
Study ledger prewarms, and Meld basis validation are unchanged. The default
CLI no longer creates or refreshes those artifacts. Automation that depended
on that implicit side effect must add `--ledger` (or `--refresh` when replacing
an exact reviewed slot).

The lightweight prompt still reads the complete bounded selected frames in one
turn. It reduces output obligations and review lifecycle, not input disclosure
or the need for a model to understand both peers. Future latency work may add
a validated hierarchical reconciler, but batching is not enabled by this
change.

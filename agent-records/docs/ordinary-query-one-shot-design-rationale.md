# Ordinary Query one-shot design rationale

## Motivating scenario

An ordinary Query over `task-1` selected 17 visible Contexts and froze 378
search candidates: 376 Memories, one query-only public projection, and one
Compare artifact. The previous execution first asked the shared Find ranker for
at most eight candidates and then started an isolated answer-model turn over
only the primary subset. A valid ranking could choose only the aggregate
Compare artifact, so the final answer exposed one Reference even though the
question asked for examples from both sides and a conflict/problem assessment.
Raising the cap to 50 would enlarge but retain that recall bottleneck.

## Decision

Ordinary Query no longer calls the Find ranker. It freezes the complete
candidate corpus, assigns temporary `mN` aliases, preflights one aggregate
provider turn, and sends every frozen evidence projection to a single
`gpt-5.6-sol` completion with reasoning effort `none`. Provider contract
version 2 returns:

- one typed outcome distinguishing full, partial, absent, related, no-related,
  and ambiguous results;
- ordered natural-language blocks classified as supported claims, input
  interpretations, or Context-bounded scope limitations; and
- every temporary source alias directly supporting each supported claim.

The prompt requires the combined blocks to address every part of the question.
For comparisons it asks for evidence from each represented side when available,
plus separately supported aggregate conflict or issue conclusions. Specific
Memories are preferred for examples; an aggregate artifact can support a
relation-set assessment but should not replace specific evidence that is
already present in the supplied corpus.

This is `WHOLE_FRAME_ONLY`, not a hidden batching plan. If the complete prompt
exceeds the shared 1,000,000-character provider-input contract, Query fails
before provider connection and asks the person to narrow the selected Context
range. It never truncates an oversized Memory, drops candidates, publishes a
partial answer, or reconciles independently generated shards as if they were
one global review.

The one-shot CLI also accepts `-a/--all` as the ordinary Query spelling for
`PROFILE · ALL READABLE CONTEXTS`. The command snapshots the active current
Context, freezes the Profile-readable catalog, expands it to concrete canonical
names, and places that exact tuple in `OrdinaryQueryRequest.target_names`.
`PROFILE` is never passed to storage or persisted. This form is mutually
exclusive with `--context` and with the two-positional query-only-view form;
query-only Grant routes remain a distinct typed Source catalog. Because all
frozen contributors enter one provider frame, granted Sources must authorize
the applicable `DERIVE` and cross-domain `COMBINE` use before provider
construction.

## Citation contract

The model never owns display numbers. It may return only allowlisted temporary
aliases and is explicitly told not to write `[1]`, a `References` heading, or a
bibliography. The local decoder rejects unknown or duplicate aliases, empty
source lists on supported claims, any source on input interpretations or scope
limitations, line breaks or numeric citation markers in model prose,
outcome/role-order mismatches, and malformed structures.

After validation, the host walks answer blocks in order. The first use of an
alias receives `[1]`, the next new alias receives `[2]`, and later reuse keeps
the original number. The host appends those markers to the corresponding block
and renders each existing typed Reference object as one logical
`[N] content — UID prefix, Context, alias` row through the operation-neutral
Source Reference projection. Different Sources therefore stay
self-contained without repeating a two-line metadata header, and adjacent rows
have no blank separator. Stored line breaks are folded so cited content cannot
create a sibling row or heading. Kind and the full UID remain in the typed
evidence and public citation projection even though the compact terminal row
does not display kind. Durable UIDs never enter the model prompt. This makes
`[1]` work like an actual citation: the prose marker and Reference row share one
host-validated identity rather than trusting a number fabricated in generated
text.

Answer intent and citation identity are separate concerns. The implemented
case-derived answer contract and its calibration method are recorded in
`query-case-derived-answer-design-rationale.md`. Provider contract version 2
distinguishes direct, partial, absent, and observational results without
weakening this document's host-owned alias and numbering boundary.

Only the row facts and punctuation are shared with provider-free Find. Query retains
first-use citation numbering, evidence alias validation, and used-reference
selection; Find retains match ordering, exact spans, MemoryRef provenance, and
its own preview policy. Sharing `SearchAnswerEvidence` itself was rejected
because a provider-free exact match has no Query evidence alias or citation
selection semantics.

## Boundaries and alternatives

Semantic Search is intentionally unchanged. Its result-list semantics still
use `TOP_K_RERANK`, including staged group-preserving retrieval when required.
Query-only authority routes retain their authentication, concealed source,
grant revalidation, and session boundaries; an explicitly configured non-Codex
provider is not overridden.

A top-k value of 50 was rejected because it still lets the ranking stage decide
which side or sub-question the answer model can observe. A second provider turn
used only to renumber citations was also rejected: aliases can be validated and
numbered deterministically by the host. Sol/none was selected for the new
whole-corpus synthesis contract after a local same-question comparison showed
better caution around aggregate “no issue” evidence; this observation is a
scenario check, not a general quality or latency proof.

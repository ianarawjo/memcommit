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
`gpt-5.6-sol` completion with reasoning effort `none`. The structured response
contains both:

- ordered natural-language answer blocks; and
- every temporary source alias directly supporting each block.

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

## Citation contract

The model never owns display numbers. It may return only allowlisted temporary
aliases and is explicitly told not to write `[1]`, a `References` heading, or a
bibliography. The local decoder rejects unknown or duplicate aliases, empty
source lists on answer blocks, line breaks or numeric citation markers in model
prose, ambiguous answer/no-answer combinations, and malformed structures.

After validation, the host walks answer blocks in order. The first use of an
alias receives `[1]`, the next new alias receives `[2]`, and later reuse keeps
the original number. The host appends those markers to the corresponding block
and renders the existing typed Reference objects with local UID prefix,
Context, kind, and bounded content excerpt. Durable UIDs never enter the model
prompt. This makes `[1]` work like an actual citation: the prose marker and
Reference block share one host-validated identity rather than trusting a number
fabricated in generated text.

## Boundaries and alternatives

Find is intentionally unchanged. Its result-list semantics still use
`TOP_K_RERANK`, including staged group-preserving retrieval when required.
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

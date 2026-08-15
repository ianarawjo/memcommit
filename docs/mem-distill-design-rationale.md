# `mem distill` design rationale

## Status

Implemented as a first local Context-to-Context vertical slice. The command
can analyze an exact Context or its readable descendants, optionally under a
Goal, and can create one fresh local Result Context after review. A dedicated
saved-session TUI and durable grant-derived results remain future work.

## Meaning

Distill reduces a Goal and/or concrete Context evidence into fewer reusable,
independently meaningful Rules. It is not defined by a top-down or bottom-up
direction: examples can support a Rule, a Goal can support a Rule, and a Goal
can constrain which Rules are relevant when Context evidence is also present.

This differs from neighboring operations:

- Summarize produces process-local comprehension and creates no Memory.
- Atomize restructures existing meaning into independently reviewable
  Memories and may change its Source after Apply.
- Distill proposes abstractions across a complete evidence frame, leaves the
  Source unchanged, and materializes only reviewed Rules into a fresh Result.
- Induct is an inner Ground primitive that proposes one scoped Rule delta after
  a reviewed case exposes a gap; its distinction is delta scope, not the use of
  examples.

## Contract

One request freezes a Source Context frame plus an optional Goal. Every
proposed Rule contains standalone content, rationale, whether the Goal
materially supports it, exact supporting Source Memory UIDs, and exact
boundary or contrast Memory UIDs. Every Source Memory must either be cited by
at least one Rule or be named in the analysis-wide outside set. A Memory cannot
be silently omitted, and it cannot be both outside and cited.

The Goal is data and may support a normative Rule, but it cannot make an
unsupported factual claim true. A Goal-only Rule is allowed when an empty
Context is selected, while Context-only distillation remains valid when no
Goal is supplied. With neither Goal nor ordinary Source Memory, analysis fails
before provider connection.

Distill declares `WHOLE_FRAME_ONLY` semantic execution. Cross-Memory evidence,
exceptions, and boundaries can affect every Rule, so the first version rejects
an oversized frame rather than partitioning it without an operation-owned
global reconciliation pass. The provider sees aliases rather than durable
Memory UIDs; returned aliases are resolved and validated locally.

## Apply and provenance

Analysis is read-only. Apply requires a fresh Result Context and never changes
the Source. Before publishing, the complete frozen frame is rebuilt and every
local Source Context identity and digest is rechecked under the require-new
Store transaction. Each Result Memory has a deterministic identity derived
from the exact analysis and Rule proposal.

The Result checkpoint records the analysis digest, Source scope and digest,
Goal and Goal digest, provider-contract version, and per-Rule support and
boundary UIDs. This preserves why each abstraction was materialized without
pretending the output is a lossless copy of every Source Memory.

The first slice rejects any frame containing a granted Context before provider
connection. A future grant-aware analysis and output must require the
appropriate `DERIVE`, `EXPORT`, retained-analysis, and target acceptance
permissions rather than silently deriving or copying authority-owned content
into a local store. A dedicated saved Resolution Workbench is also not
presented as implemented in this first slice.

## Ground compatibility

New Ground Rules use direction-neutral `DISTILLED` provenance whether their
support comes from a Goal, Memories, or both. `DISTILLED_FROM_GOAL` and
`INDUCED_FROM_CASES` remain accepted legacy persisted tokens and render as
`DISTILLED`; they are no longer emitted for new Rules. `JOINTLY_REVISED`
continues to identify a reviewed revision rather than a source direction.

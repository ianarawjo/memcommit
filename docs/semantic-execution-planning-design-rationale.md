# Semantic execution planning design rationale

## Motivation

The first semantic operations were bounded one-shot research prototypes. Their
limits evolved locally: Find, Update, Atomize, Translate, and the quality
finders used 200,000-character payload guards; Compare and Meld used 400,000
characters plus separate item limits; other operations retained their own
one-shot boundaries. The canonical 150-by-150 Task 2 frame exposed why one
scalar was insufficient: a 200-item Compare boundary could produce a reviewed
ledger that a 300-Memory Meld was then unable to consume, so Meld's local item
limit was raised instead of changing the execution model.

The immediate failure that motivated this shared layer was an interactive Find
over 106 exact checked Contexts with embedded reach enabled. Its corpus crossed
the former 200,000-character guard before provider connection even though the
configured provider supports a substantially larger turn. A later preflight
also rejected the canonical Task 1 Update solely because 75 Source candidates
plus 300 Target candidates produced a theoretical 375-operation maximum, even
though its encoded input was 82,945 characters and its studied complete result
contains 77 changes. These failures established that lower operation-local
corpus and candidate-count ceilings were preventing supported provider work.

Aggregate semantic adapters now share a 1,000,000-character effective provider
input capacity. Candidate, expected-output, schema, and relation counts remain
observable workload axes, but candidate cardinality alone is not a rejection
condition. Structural response bounds still derive from the frozen candidate
sets, and validation continues to reject unknown, duplicate, uncovered, or
otherwise invalid results.

## Boundary

`provider.complete()` remains one provider call. It cannot infer whether an
arbitrary prompt is retrieval, an exhaustive relation ledger, a directional
mutation plan, a holistic summary, or selective curation. Automatic splitting
inside the provider adapter would therefore change operation meaning.

`memcommit.semantic_execution` sits above the provider and below operation
adapters. It owns only operation-neutral mechanics:

- a vector budget;
- one-shot, staged, or rejected planning;
- stable group-preserving packing;
- exactly-once input-exposure coverage;
- all-batches-before-result execution and common progress;
- complete left-batch by right-batch scheduling; and
- connected components over validated positive relation observations.

Operations still own candidate construction, authority, disclosure, provider
prompts and schemas, semantic reconciliation, durable state, and application.

The shared coverage layer also supplies the narrow provider-I/O contract used
by relation operations: an exact-count source-assignment array, a frozen alias
enum, and a decoder that proves every alias appears once. Compare and Meld use
that contract to assign each Source Memory to one semantic relation, then
reconstruct their operation-specific PEER or directional relation shapes
locally. This is output coverage inside one bounded call, not staged execution
or evidence that relation judgments are semantically complete.

## Budget contract

`BudgetVector` records independent axes:

| Axis | Meaning |
| --- | --- |
| `input_chars` | Deterministically serialized provider payload size |
| `item_count` | Frozen Source and Target items presented to the operation |
| `schema_chars` | Structured-output schema size, including alias enums |
| `expected_output_items` | Expected or worst-case result cardinality |
| `relation_edges` | Pair or bipartite relation space implied by the frame |

`BudgetLimits` may constrain any subset. Reaching one axis does not imply that
another is safe: many short items can overflow a coverage schema or relation
ledger while one long Memory can overflow input with an item count of one.
Character accounting remains deterministic because the current configured
provider does not always expose a resolved model-specific tokenizer or context
window. The vector can later accept a trustworthy token estimate without
collapsing the existing axes.

For the current provider contract, aggregate policies constrain only encoded
input characters. Item, output, and relation axes are diagnostics and staging
inputs, not independent hard ceilings. A future runtime capability handshake
may replace the shared 1,000,000-character value with model-specific token and
reserved-output budgets without changing operation semantics.

## Strategies

Every operation declares one staged semantic strategy:

| Strategy | Required reconciliation |
| --- | --- |
| `TOP_K_RERANK` | Rank every shard, retain every shard's validated shortlist, then globally rerank their union |
| `COVERAGE_MAP` | Return exactly one validated result for every frozen input and restore canonical order |
| `BLOCK_RELATIONS` | Expose complete block coordinates, reconcile positive relation components, then rebuild exhaustive dispositions and issues |
| `MAP_PLUS_GLOBAL` | Map item-local judgments, then run the complete cross-item quality or consistency pass |
| `HIERARCHICAL_REDUCE` | Reduce bounded source-linked reports and explicitly preserve the hierarchy's evidence limits |
| `WHOLE_FRAME_ONLY` | Never partition; reject or require a smaller frame or more capable provider |

A strategy declaration is not an implementation claim. `staged_supported`
remains false until the operation adapter implements and validates its required
reconciler. The planner then rejects an over-budget frame rather than returning
a plausible-looking partial result.

## Implemented staged paths

### Ordinary Find

Find preserves Context ownership as its first packing boundary. Multiple small
Contexts share one batch; an oversized Context is subdivided only at candidate
boundaries. Every candidate appears in exactly one first-stage request. Each
batch returns a validated primary or related shortlist. If any primary exists,
it is ordered first, but it does not suppress another shard's related fallback
before the global judge can compare them. The validated union receives one
final reranking call, which restores the ordinary mutually exclusive primary
or single-related-query result contract.

If one candidate cannot fit, or if the complete shortlist still cannot fit,
Find fails without truncating stored content. Small corpora retain exactly one
provider call. Temporal Find currently remains guarded one-shot because its
provider returns a coupled subject/anchor/relation plan rather than ordinary
ranked candidates; independently planned timeline shards cannot yet be merged
without a temporal-plan agreement contract.

### Ordinary Query

Ordinary Query declares `WHOLE_FRAME_ONLY`. Unlike Find, it does not produce a
top-k result list: one Sol/none completion reviews the complete frozen candidate
corpus and returns answer blocks plus the temporary evidence aliases supporting
each block. The host validates those aliases and assigns display citation
numbers without another provider turn. A corpus beyond the shared input bound
fails before provider connection; Query does not inherit Find's staged ranker,
silently shortlist the frame, or reconcile separately drafted partial answers.

### Translate

Translate uses `COVERAGE_MAP`. Small selections retain one provider call. A
large selection is split only between Memories, every global candidate alias
is sent once, every batch must return complete validated coverage, and batch
proposals are restored in source order. A failed batch exposes no plan. One
oversized Memory fails before provider connection.

The existing `provider_response_sha256` remains a single checkpoint field. For
one call it retains the historical raw-response digest. For staged translation
it hashes the canonical ordered tuple of raw batch responses. The batch count
and individual response digests are not yet durable metadata; this is an
explicit provenance limitation rather than a claim that staged work was one
physical call.

## Relation and holistic operations

Compare, Meld, Update, Conflict, Atomize quality, Atomize grounding, Summarize,
and Rationale now declare shared policies and budget vectors, but their staged
reconcilers are not enabled. Their existing exhaustive or source-linked result
contracts remain one-shot below the bound and fail closed above it.

Update records the complete theoretical workload of one addition per Source
plus one mutually exclusive edit or removal per Target, but does not confuse
that candidate-derived maximum with provider capacity. Its output schema and
parser derive structural maxima from the exact frozen Source and Target sets;
there is no separate 200-operation or 50-source-reference gate. An Update
review turn still budgets the Source, Target, current reviewed proposal, and
guidance together, so revision cannot bypass the 1,000,000-character input
boundary.

The shared block-matrix scheduler makes every left-batch/right-batch coordinate
observable once without allocating a Cartesian list of item pairs. The shared
component builder can merge validated positive hyperedges and retain unmatched
singletons. Those mechanics alone do not prove recall, choose a relation kind,
merge conflicting batch judgments, reconstruct globally concise reports, or
preserve issue and proposal provenance. An adapter must solve those semantics
before changing `staged_supported` to true.

The retained Task 2 evaluation pipeline is evidence for this caution. Its
bidirectional retrieval and global component reconciliation improved scale,
but candidate recall and final subset precision varied by provider and stage.
Production Compare or Meld must not label such a retrieval projection an
exhaustive ledger without an explicit coverage contract.

## Whole-frame selective curation

Forget and Sever declare `WHOLE_FRAME_ONLY`. They share the 1,000,000-character
provider-capacity preflight and have no independent item-count gate. The
complete frozen Source and criterion frame must still appear in one turn and
return one decision per Source Memory because neighboring Source Memories may
affect a decision. A Forget review turn also budgets its complete retained
dialogue and fails before the provider rather than treating follow-up history
as exempt.

## Whole-frame Conformance

Case and Context Conformance both declare `WHOLE_FRAME_ONLY`. Case Conformance
must expose every input to the same frozen Rule set while withholding expected
outputs, then return exactly one prediction or unresolved disposition per case.
Context Conformance must judge every Rule against the complete target frame and
account for every target Memory as cited evidence or explicitly outside. Hidden
batching would require operation-owned reconciliation for cross-case Rule
interpretation and Context-wide mixed evidence; neither operation currently
claims such a reconciler.

## Whole-frame Resolve

Resolve declares `WHOLE_FRAME_ONLY`. The initial Fit judgment, candidate
generation, independent grounding/information-preservation verification, and
final Fit judgments each operate on a complete frozen direct-Memory frame or
complete candidate post-image. A complete block matrix would not establish
that a repair preserves facts across shards, and independent local repairs
could introduce new cross-batch incompatibilities. Resolve therefore rejects
an oversized frame before provider construction or before publishing an
incomplete analysis; it does not enable hidden batching.

## Migration scope

This layer covers aggregate Context operations whose candidate, relation,
schema, or output cardinality grows with the selected frame. It is not a
wrapper around every provider call. Fixed one-case calibration gates, bounded
Ground authoring dialogue, and the legacy non-public Integrate batch protocol
retain their own contracts for now. If any of those begins accepting an
unbounded Context frame, it must declare an operation policy rather than rely
on transport-level splitting.

## Failure, progress, and compatibility invariants

- Candidate aliases and frame contents are frozen before planning.
- Group packing is stable and deterministic.
- A group is kept whole when it fits; only an oversized group may split at
  operation-approved item boundaries.
- A single oversized item is never truncated.
- Batch input identities are unique and must complete exactly once.
- Exceptions publish no partial semantic result.
- `BATCH`, `RECONCILE`, and `COMPLETE` progress is presentation-only state.
- Existing one-shot prompts, local response validation, session schemas, CAS
  checks, permissions, and apply boundaries remain authoritative.

## Alternatives rejected

Retaining lower per-operation character ceilings and fixed candidate-count
gates was rejected because those limits contradicted the effective provider
capacity and made canonical Study frames unreachable. The shared 1,000,000
character value is an explicit current-provider contract, not a claim that
characters are a permanent substitute for model capabilities. Generic
provider-level prompt splitting remains rejected because it cannot preserve
operation meaning. Silent local semantic prefiltering remains rejected because
it can remove the only relevant candidate without a recall receipt. Treating a
block matrix or connected components as a final Compare/Meld answer remains
rejected because exposure coverage is not semantic reconciliation.

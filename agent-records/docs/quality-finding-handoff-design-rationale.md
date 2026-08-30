# Quality Finding Handoff Design Rationale

## Problem

`find-redundancies`, `find-ambiguities`, `find-conflicts`, and Dedun's shared
analysis begin as read-only observations. A question or possible reading in a
finding is report evidence, not a prompt for an answer. The finder browser
therefore has no selection, response, obligation, or draft state. CLI, TUI,
Python, and agent adapters must not reconstruct different next-operation
requests from rendered text.

The motivating Task 1 flow is a staged pipeline:

`merge -> dedup -> dedun -> resolve -> audit`

Each stage has a different meaning and must freeze its own source and authority.
Merge combines frames, Dedup removes exact copies, Dedun applies complete
exact-plus-semantic redundancy, Resolve repairs a non-fitting direct-Memory frame, and
Audit checks the resulting state. No stage implicitly performs a later one.

## Application contract

`memcommit.application.capabilities.memory_issue_analysis.handoff`
owns an adapter-neutral
`QualityFindingHandoff`. Every handoff records:

- the exact finding identity and frozen finder-frame digest;
- each readable source Context UID, public display name, and ordered
  direct-Memory digest;
- the finding Memory UIDs and their public owner Context names;
- classification, qualifiers, reason, question, and proposed readings; and
- the intended next-operation route.

`qualifiers` remains a version-1 envelope field for adapter compatibility, but
current Conflict handoffs leave it empty. The retired `scope_dimensions`
taxonomy is not reconstructed from prose and is not required by Resolve;
Conflict's exact classification, reason, and question carry the semantic
evidence used at the handoff boundary.

The routes are deliberately explicit:

| Finding | Route | Current execution status |
| --- | --- | --- |
| Complete DUN redundancy | internal `DEDUP` compatibility value | Public evidence uses `REDUNDANCY` / `DEDUN` and executes as `mem dedun` |
| Ambiguity | `CLARIFY` | Typed route only |
| Conflict | `RESOLVE` | Same-Context conversion implemented |

The version-1 receipt retains its `QualityFindingReviewDraft` field for wire
compatibility with previously serialized handoffs. The read-only finder
adapter always emits the empty value; only a separately answerable legacy
review consumer may populate it. A receiving operation never treats that
compatibility field as submitted guidance.

The receipt has one strict JSON form. Decoding rejects unknown or missing
fields, duplicate JSON keys, invalid nested values, unsupported contract
versions, and content whose deterministic finding UID no longer matches. The
receipt contains identities and semantic finding metadata, not full source
Memory contents. No command automatically writes it to a cache or file.

## Conflict to Resolve

`conflict_handoff_to_resolve_request` converts one handoff to a normal
`ResolveRequest` only when the finder analyzed exactly one Context and both
conflicting Memories are directly owned by it. The request uses full Memory
UIDs as selectors and carries a `ResolveSourcePrecondition` containing the
Context UID, public display name, and complete ordered direct-Memory digest.

`run_resolve` compares that precondition with its newly frozen frame before
semantic preflight or provider connection. An added, removed, reordered, or
edited direct Memory, a changed Context identity, or a changed public target
name fails closed and requires the finder to run again. The whole direct frame
is checked because Resolve independently evaluates Fit over that whole frame,
not only over the reported pair.

The handoff carries no Grant or mutation authority. Resolve re-resolves the
public target, freezes the current Grant binding and effect capabilities, and
retains its existing Apply-time revalidation. `UPDATE` remains the baseline;
`CREATE` and `DELETE` remain explicit opt-ins, and `DELETE` still requires
separately submitted grounding guidance.

## Adapter flow

Every adapter receives the same application-owned handoff:

- Python exposes `find_redundancies`, `find_ambiguities`, and `find_conflicts`
  on `MemCommitClient`, returning `QualityFindResult.handoffs`;
  independent `find_duplicates` returns a provider-free
  `ExactDuplicateFindResult`. A conflict is
  passed unchanged to `resolve_conflict_finding`.
- CLI `mem find-conflicts --handoff-json` prints one canonical receipt per
  finding. `mem resolve --finding-handoff JSON` decodes that receipt and uses
  the same conversion. Ordinary finder output remains read-only.
- The interactive conflict workbench offers `Resolve selected conflict` in
  To Do only for a single-Context finder frame. It emits the exact selected
  item UID and opens the ordinary Resolve review. It does not apply anything
  at the handoff boundary.
- The `memcommit_quality_find` agent/MCP tool returns the same JSON receipt.
  `memcommit_resolve` accepts it as `finding_handoff`; context and Memory
  selector fields are then forbidden so an adapter cannot retarget it.

All four adapter paths converge on `ResolveRequest.source_precondition`; none may
synthesize its own digest, target, Memory selector, or guidance.

## Memory Issue Analysis ownership

On 2026-08-30 the shared package moved from the provisional
`reviewing.quality` name to `reviewing.memory_issue`, then moved directly to
`application.capabilities.memory_issue_analysis` after the judgment was also
needed outside a review phase. Duplicate, Ambiguity, and Conflict outputs are
model-assisted candidates for review, not proof that a Memory has an
open-ended quality defect. Existing type names remain unchanged in this
ownership step so public Python values and serialized handoffs are not silently
migrated with the physical package.

The shared family is split by judgment shape: Context-aware ambiguity enters
`reading_analysis`; redundancy and conflict enter `relation_analysis`; models,
provider mechanics, Source freezing, report projections, response workbenches,
and typed handoffs remain narrower peer modules. The workbench and handoff do
not make analysis mutating: they only preserve typed evidence for a later
operation that independently validates its authority and materialization.

The four public discovery routes now have symmetric console package names and
explicit application owners: `find_duplicates`, `find_redundancies`,
`find_ambiguities`, and `find_conflicts`. Their `application.py` modules own
request validation, readable authority/Source preparation where applicable,
and typed analysis results. Shared issue/report contracts and analysis
entrypoints stay under `capabilities.memory_issue_analysis`, so Audit and other
operations can reuse a judgment primitive without calling a peer Find
operation or inheriting its presentation workflow.

## Deliberate boundaries

- Cross-Context conflicts do not enter Resolve v1. Repairing them requires an
  operation whose post-image and ownership semantics cover multiple Contexts;
  silently shrinking the finder frame to one owner would change the question.
- Complete DUN redundancy and ambiguity evidence identifies its receiving
  operation but does not pretend that Resolve implements Dedun or Clarify.
- Find Redundancies does not install a handoff executor. Dedun alone accepts
  every eligible redundancy finding from its complete frame and independently
  revalidates the deterministic survivor and Apply boundary.
- Serialized receipts are transferable but intentionally not durable sessions.
  Callers that retain them own that file or message lifecycle; MemCommit does
  not create a new cache containing finding reasons, questions, or answers.
- Dedun and Clarify remain named routes rather than fake Resolve variants.
  Dedun consumes the source-bound redundancy handoff while retaining its own
  disposition and materialization semantics; a future Clarify executor must do
  the same for ambiguity evidence.

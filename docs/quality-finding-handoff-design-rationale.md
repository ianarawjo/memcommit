# Quality Finding Handoff Design Rationale

## Problem

Dedun discovery, `find-ambiguities`, and `find-conflicts` begin as read-only
observations. Their Resolution workbench can collect process-local responses,
but a response is not itself an executable request, mutation authority, or a
freshness guarantee. CLI, TUI, Python, and agent adapters therefore must not
reconstruct different next-operation requests from rendered text.

The motivating Task 1 flow is a staged pipeline:

`merge -> dedup -> dedun -> resolve -> audit`

Each stage has a different meaning and must freeze its own source and authority.
Merge combines frames, Dedup removes exact copies, Dedun decides semantic
redundancy disposition, Resolve repairs a non-fitting direct-Memory frame, and
Audit checks the resulting state. No stage implicitly performs a later one.

## Application contract

`memcommit.quality_finding_handoff` owns an adapter-neutral
`QualityFindingHandoff`. Every handoff records:

- the exact finding identity and frozen finder-frame digest;
- each readable source Context UID, public display name, and ordered
  direct-Memory digest;
- the finding Memory UIDs and their public owner Context names;
- classification, qualifiers, reason, question, and proposed readings; and
- the intended next-operation route.

The routes are deliberately explicit:

| Finding | Route | Current execution status |
| --- | --- | --- |
| Semantic redundancy | internal `DEDUP` compatibility value | Public evidence uses `REDUNDANCY` / `DEDUN` and executes as `mem dedun` |
| Ambiguity | `CLARIFY` | Typed route only |
| Conflict | `RESOLVE` | Same-Context conversion implemented |

The handoff also snapshots the workbench response as
`QualityFindingReviewDraft`. This name and type are a safety boundary: merely
typing text or selecting a review option does not submit Resolve guidance.

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

- Python exposes `find_duplicates`, `find_ambiguities`, and `find_conflicts`
  on `MemCommitClient`, returning `QualityFindResult.handoffs`. A conflict is
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

## Deliberate boundaries

- Cross-Context conflicts do not enter Resolve v1. Repairing them requires an
  operation whose post-image and ownership semantics cover multiple Contexts;
  silently shrinking the finder frame to one owner would change the question.
- Semantic redundancy and ambiguity evidence identifies its receiving
  operation but does not pretend that Resolve implements Dedun or Clarify.
- Serialized receipts are transferable but intentionally not durable sessions.
  Callers that retain them own that file or message lifecycle; MemCommit does
  not create a new cache containing finding reasons, questions, or responses.
- Dedun and Clarify remain named routes rather than fake Resolve variants.
  Their future executors must consume the same source-bound handoff while
  retaining their own disposition and materialization semantics.

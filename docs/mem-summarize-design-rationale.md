# `mem summarize` and the shared understanding unit

## Status

Implemented. This note defines the reusable `UnderstandingSummary` embedded in
Atomize and Compare and the standalone read-only `mem summarize` producer.

## Decision

Only `WHAT MEM UNDERSTOOD` is common. Operation-specific accounts remain owned
by their operation:

```text
UnderstandingSummary
  text
  source Memory identities

Atomize
  UnderstandingSummary
  WHAT HAPPENED
  WHAT REMAINS UNRESOLVED

Compare
  UnderstandingSummary
  WHAT BOTH CONTAIN
  WHAT DIFFERS
  side-only reports
```

`mem summarize [CONTEXT]` independently produces and renders only the shared
unit. It does not run Atomize classifications, ambiguity or conflict scans, a
comparison ledger, or any Context mutation. It is comprehension, not
distillation: no summary Memory or checkpoint is created.

Atomize retains its existing serialized overview shape for compatibility, but
its `understood` value is now the common type. Compare retains the serialized
`overview` string accepted by earlier analysis schemas while exposing the
validated in-memory value as `analysis.understanding`; `analysis.overview`
remains a compatibility text property. Both use the common terminal renderer.

## Standalone command contract

The command defaults to the recursively loaded Context graph because its job
is to replace full-tree reading with one comprehension report. `--direct`
restricts the frame to direct ordinary Memories. A shared or cyclic embedded
Context is visited once by stable Context identity. Ordinary Memory order is
preserved and temporary provider aliases are mapped back to exact local Memory
UIDs.

The normal output deliberately omits `WHAT WAS INCLUDED` and
`WHAT WAS OUTSIDE THIS SUMMARY` sections. Those are execution-scope facts, not
semantic understanding. The compact header states only `READ-ONLY` and
`RECURSIVE` or `DIRECT`; scope validation remains an internal invariant.

`MemoryRef` and `QueryContextRef` content does not enter this first summary
frame. Query-only content is never opened. An empty ordinary-Memory frame is
reported deterministically without connecting a provider. Oversized input is
rejected rather than truncated or divided into hidden provider calls.

The provider returns one concise natural-language paragraph plus temporary
source aliases. Unknown or duplicate aliases, duplicate JSON keys, list-shaped
prose, over-limit output, and source-free nonempty claims fail closed. Output
is terminal-escaped by the common renderer.

After the semantic call, the command rebuilds the same frame and compares its
digest before publishing output. A granted READ frame additionally freezes and
revalidates the exact grant binding. Results are process-local: this avoids
copying authority-derived prose into the participant store and avoids creating
a stale summary cache before a separately designed revocable artifact exists.

## Reuse boundary

Common type, evidence binding, schema helpers, and rendering are reusable.
Operation-specific prompt context and the resulting text are not automatically
interchangeable. A summary may be reused as data only when its complete frame
and operation-neutral understanding contract match; equal-looking headings do
not prove equal evidence.

Physical provider batching is independent of this logical boundary. Atomize
may continue returning its understanding, classifications, and quality results
in one completion while validating the understanding as its own unit. A later
refactor may share more prompt composition without changing this contract.

## Intentional limitations

- No persistent summary cache or `--refresh` lifecycle exists yet.
- No query-only summarize route is inferred; `mem query` remains authoritative.
- No responsibility judgment is inferred from content or grant ownership.
- Compare's historical overview serialization is not migrated implicitly.
- `WHAT HAPPENED`, unresolved findings, and comparison category reports are
  not generalized into the understanding unit.

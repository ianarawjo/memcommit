# Semantic result memorization design rationale

Last reviewed: 2026-08-29.

## Motivating problem

Distill and Elaborate can turn one provider result into several durable
Memories in an existing Context. The shared implementation was historically
named `semantic_add_runtime` and later placed under `operations.add` because
its final effect was `ADD`. Exact user-supplied Add never called that module.
The placement therefore conflated the Add operation with an ADD-shaped effect,
and the generic `semantic_runtime` name did not identify the state transition.

## Chosen ownership and language

`memcommit.application.capabilities.semantic_result_memorization` owns the
shared transition. In this repository, **memorize** means converting the
complete result of one semantic operation into durable ordinary Memories. It
does not mean training or changing a provider, and it does not create a
special Semantic Memory type.

The capability is outside both `operations.add` and the broad `semantic`
package. `semantic` remains a qualifier for the result's origin rather than a
container that claims unrelated prompting, classification, disclosure, and
publication responsibilities.

## Contract

One memorization follows this sequence:

1. Resolve Source and Target names from one frozen Current snapshot.
2. Freeze the existing local Target's canonical name, UID, and record digest
   before provider construction.
3. Let the owning operation freeze its complete Source and produce the result.
4. Revalidate the Target UID and digest, then reject stale output before any
   mutation.
5. Convert every nonblank result content into a new ordinary Memory in order.
6. Preserve exact Source bindings, omitting a duplicate binding when Source and
   Target are the same Context and Target CAS already protects the pre-image.
7. Save one checkpoint under the originating operation name and return every
   created Memory UID plus the checkpoint UID.

The result is all-or-none. No partial Memory set or success receipt is
published after validation, CAS, source-binding, or storage failure.

## Boundaries

Exact Add retains its own terminal-independent request, provenance, Grant,
append, and receipt contract under `application.operations.add`; it neither
imports nor delegates to memorization. Both paths may use the lower-level
`ops.add_many` domain operation, but their concurrency and checkpoint meanings
remain different. Exact Add may reload and append to the latest same-identity
Context, while semantic result memorization rejects any Target digest drift
across provider work.

The capability does not call a provider or decide what the result means. It
also does not own JSON, locks, or filesystem representation; `MemoryStore`
retains those persistence mechanics. Ground may reuse the frozen Target value
during preparation, but Ground's explicit adoption and Undo unit remain
Ground-owned operations rather than memorization publication.

## Alternatives considered

- Keeping the implementation under `operations.add` was rejected because an
  ADD effect is not the Add operation.
- Moving it under `capabilities.semantic` was rejected because `semantic` names
  a broad processing quality rather than this capability.
- `materialize` was rejected as the canonical verb because Distill already
  uses materialization for a distinct require-new Result Context boundary.
- `publish` accurately described durability but did not make the result-to-
  Memory conversion explicit in the Memcommit domain language.

## Limitations

The current capability accepts local Targets and operation-owned checkpoint
arguments. Authority-aware generated-result acceptance and a typed shared
checkpoint-argument schema remain separate future decisions. The historical
root-module inventory key `semantic_add_runtime` remains only as a record whose
canonical target now points at this capability; no runtime compatibility path
is retained.

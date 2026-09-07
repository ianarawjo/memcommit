# Compare saved-analysis lifecycle

## Status

Compare now exposes the same ordered analysis through the CLI, public Python
facade, versioned agent adapter, and MCP projection. The operation is read-only
with respect to both source Contexts. Its only durable result is the latest
analysis slot for one ordered `(REFERENCE, COMPARED)` Context pair.

The public lifecycle is deliberately small:

```text
run(reference, compared, exact scope)
  -> reuse an exact current saved analysis
  -> materialize an authorized hidden exact/equivalent prewarm
  -> return an unsaved safe projection
  -> or run one exhaustive provider turn and CAS-save the complete analysis

open(analysis_uid)
  -> load the exact latest-slot artifact
  -> revalidate its complete source scopes and provenance
  -> return the analysis plus an opaque canonical-digest version

refresh(analysis_uid, expected_version)
  -> verify the exact reviewed artifact before provider/cache work
  -> reload and authorize the same ordered names and saved scope
  -> run one fresh exhaustive provider turn
  -> replace the latest slot only if both its UID and full version still match
```

## Why Compare is not a generic review-and-Apply session

A Compare analysis has no target Context, proposed changes, answerable turns,
readiness state, or Apply authority. The provider result is the read-only
artifact itself. Creating or refreshing that artifact can write one analysis
file, but it never mutates either source Context, creates a checkpoint, or
enters Undo/Redo history.

Adding a synthetic Apply step would make a read-only result look like a pending
Context mutation and would give agents an unnecessary second action. Compare
therefore has `run`, `open`, and `refresh`, not `review` or `apply`.

## Exact revision and retry behavior

The stored analysis UID identifies one provider result. It is not sufficient as
an optimistic revision token because a malformed external writer could retain
the UID while changing another field. Persistence now compares both:

- the expected analysis UID; and
- the canonical digest of the complete saved analysis payload.

For Grant-bound storage, the Grant binding and retention mode remain separately
revalidated authority metadata; the optimistic version covers the analysis
payload that Refresh replaces.

Public and agent Refresh require the opaque version returned by Open. A stale
version fails before hidden-prewarm lookup, provider construction, or durable
publication. After one successful Refresh, repeating the old request fails
instead of publishing a second analysis.

The CLI's explicit `mem compare --refresh --to ...` remains a fresh command,
not an action emitted from an externally reviewed artifact. It freezes the
current slot at command start and uses the same UID-plus-digest CAS at
publication. Python and agent callers that act on a previously returned
analysis use the stricter Open-to-Refresh token contract.

## Freshness and scope

Open means “show this saved analysis as current.” It therefore rejects a
changed or missing source without calling the provider. There is one current
analysis format and no semantic ruleset revision check.
Refresh has different intent: updating a stale analysis is its purpose. It
validates the saved artifact version first, then reloads the current sources
under the original ordered names, descendant flags, and exact-Memory focus.

Exact-Memory focus has its own stored UID. It is not inferred from the presence
of neighboring Context evidence, because an explicitly selected Memory can be
the only Memory in its Context when the analysis is created. Keeping these
values independent prevents a later Refresh from broadening that selection if
neighbors are subsequently added.

Recursive session revalidation reconstructs the same flattened lexical scope
used by Compare execution. Focused retained Grant artifacts also restore their
non-actionable Context evidence because that evidence remains part of the
frozen Context digest even though it is not a relation member.

## Cache and retention boundary

The public Run route uses Compare's production cache order rather than a second
adapter-specific lookup:

1. authorize and freeze the complete requested frames;
2. reuse the exact saved latest-slot analysis when it matches;
3. try an installed exact or ancestor-equivalent hidden artifact;
4. try an allowed descendant-subset projection;
5. only then construct the provider.

A durable hidden hit is materialized through the ordinary analysis Store and
CAS boundary before it becomes visible to Open. A safe subset projection stays
`durable=False`, reports its origin, and cannot be opened or refreshed as if it
were a saved session. Refresh intentionally bypasses saved, equivalent, and
projected reuse because its requested meaning is a new live analysis.

Grant authority still determines whether a result may be retained. A
Grant-bound or retained artifact is reopened through its stored bindings and
retention mode. An authorized but unsavable result remains an explicit
ephemeral projection; the adapter never invents a durable session for it.

## Interface and dependency boundary

- `comparison_execution` owns authorization, cache ordering, provider-result
  validation, source revalidation, and latest-slot publication.
- `comparison_session_application` owns exact durable discovery, Open
  freshness, opaque versions, and reviewed Refresh preparation without
  importing terminal code.
- `MemCommitClient` projects immutable values and operation-specific public
  errors.
- `memcommit_compare` maps strict version-1 `run`, `open`, and `refresh`
  actions to that client. MCP projects the same frozen schema and handler.
- The existing CLI and TUI retain their presentation behavior and continue to
  use the same neutral execution and session lifecycle owners.

The former `commands.compare_sessions` module is now a thin picker facade over
the neutral saved-analysis functions. It retains only session-list rendering
and terminal selection mechanics.

## Deliberate non-goals

This slice does not introduce a generic persisted-session schema, change
Compare's exhaustive one-shot provider policy, add conflict resolution, or
turn Compare into Meld. It also does not make safe projected results durable.

It does not claim that an analysis file is a Context checkpoint. Latest-slot
publication remains operation metadata and intentionally stays outside
Undo/Redo.

## Verification

- public integration covers Run, exact Open, provider-free saved reuse,
  version-bound Refresh, stale-source Open rejection, stale-source Refresh,
  repeated Refresh, same-UID content drift, recursive scope revalidation, and
  zero Context checkpoints;
- Store tests prove UID-plus-digest CAS against a same-UID replacement;
- the public exact-prewarm route materializes a hidden receipt without provider
  construction;
- agent, registry, MCP, import-isolation, CLI, Grant, projection, and existing
  Compare regression tests preserve their prior behavior.

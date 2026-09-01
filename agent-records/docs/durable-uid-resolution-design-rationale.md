# Durable UID resolution design rationale

## Problem

Memcommit prints durable identifiers for Memories, Memory references, Contexts,
checkpoints, and retained Search artifacts, but its read operations historically
did not give those values one round-trip contract. Find matched only Memory
content, Search delegated ranking without exposing host-local identities, Query
omitted durable UIDs from provider evidence, Trace treated a Context UID as a
Memory selector, and Diff accepted only one checkpoint revision. A person could
therefore copy an identifier from one report and receive no result from another
read operation even though the underlying object was still readable.

## Bounded identity contract

`memcommit.application.capabilities.durable_uid_resolution` owns the shared
exact-or-unique-prefix decision. It never opens storage or enumerates a Profile.
The calling operation first freezes the complete candidate frame it is already
authorized to disclose, projects those values as typed `DurableUidCandidate`
records, and only then asks the resolver to interpret an input. An exact UID
wins. Automatic prefix interpretation starts at the eight-character display
form printed by the console, applies to both UUID and non-UUID durable artifact
identities, and succeeds only when one full UID is represented.
Several occurrences of that same full UID are one durable identity and may all
be returned; different full UIDs sharing a prefix are an ambiguity.

This separation is intentional. Identity resolution answers which authorized
object the text denotes; ContextUse, CheckpointRead, readable-catalog, and
operation-specific validation still decide whether that object may be opened
and what can be done with it. The resolver must not become a global storage
index or an authorization bypass, and an unavailable UID must not reveal
whether it exists in another Profile or outside a Grant.

## Operation behavior

Find applies local UID resolution to the Memory and MemoryRef items in its
already-frozen source frame. MemoryRef rows expose both their relationship UID
and their Source Memory UID, so either printed identity selects that authorized
row. A UID match returns the ordinary result row with explicit `matched_uids`
evidence and no fabricated content span; text occurrence counts remain text
occurrence counts. Search and ordinary Query use the shared Search candidate
frame, including the same two identities for MemoryRef candidates as well as
authorized query-route and local artifact projections. A standalone UID is
resolved before provider
construction. Search returns the exact row, while Query returns a grounded
typed Reference document. An unmatched UUID-shaped standalone input returns no
authorized result instead of inviting provider guesswork. Ordinary semantic
text continues through the existing provider contracts.

Trace adds Context UID selection through the shared typed existing-Context
operand layer, then falls through to its existing Memory/MemoryRef UID routes
only when no Context identity matched. Diff accepts either a Context identity,
which selects its newest checkpoint, or one checkpoint identity, which selects
that exact revision. A checkpoint UID resolves across the frozen ordinary-local
History catalog, while Context UID resolution also admits authorized readable
Context candidates. The adapter requests one exact
`CheckpointRead.reference((checkpoint_uid,))` window and renders that
checkpoint against its retained pre-image. Two-checkpoint chronology is not a
Diff operand contract; `mem trace CONTEXT` owns operation ordering.

## Alternatives and limitations

Putting every UID into semantic provider payloads was rejected because it
would disclose identifiers that local matching can resolve without a provider.
Building one process-wide UID index was rejected because different operations
have different readable namespaces and retained-history rights. Treating a UID
as ordinary Find content was rejected because synthetic spans would claim text
that is not present in the Memory body.

This rollout covers durable subjects naturally exposed by Find, Search, Query,
Trace, and Diff. Find remains a Memory/MemoryRef operation rather than becoming
an artifact browser. Search and Query can resolve the artifact UIDs in their
authorized corpus, while Trace and Diff retain their history-specific output.
Ephemeral focus-row, choice, turn, and internal provider aliases are not public
durable UID selectors. A later operation that prints another durable UID should
project it into its own authorized candidate frame rather than adding a new
command-local prefix parser.

The cross-kind interpretation order, access-aware Context catalogs, and
operation rollout are recorded in
[`typed-operand-resolution-design-rationale.md`](typed-operand-resolution-design-rationale.md).

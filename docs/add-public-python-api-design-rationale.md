# Add public Python API design rationale

Last verified: 2026-08-15.

## Motivation

The Add application slice owns validation, target freezing, CREATE authority,
one ordered mutation, checkpoint construction, and target CAS. A Python caller
still needed to import internal requests and infrastructure ports, however.
That would make Store/Profile ownership and error classification caller policy
rather than part of the supported library.

## Public surface

`MemCommitClient.add_memories(contents, context_name=...)` is the one public
Add method. It accepts an explicit sequence so one and many Memories retain the
same ordered-batch meaning. A bare string is rejected rather than treated as a
sequence of characters. Exact duplicates and embedded newlines are preserved.

The method returns `AddMemoriesResult`, containing the canonical public target
name, frozen Context UID, ordered `AddedMemoryResult` values, and the single
Add checkpoint UID. Internal request, Source-provenance, authority-access, and
Store-token values are not public ABI.

There is no overloaded argv-like method, file reader, paste parser, or TUI
draft object in the public API. Those are interface intake modes that all end
at the same application request.

## Store and authority boundary

The client captures the current Context once per call. Relative
`context_name` values and an omitted target are resolved from that snapshot.
The target is then frozen by identity and reloaded under the application
adapter's ordinary Store CAS before one authorized checkpoint is published.

An explicit `root=` client is local-only. It never follows host Profile Grants,
even if its Store contains an attachment with a matching name. A Profile client
may always mutate a local Context in its frozen Store. It may follow a public
CREATE-granted target only while that Profile and Store are still the active
Profile boundary at call time. Grant permission and identity are revalidated
under the authority registry lock through the authority-side save.

This asymmetry is deliberate. Local Store ownership is frozen by the client;
cross-Profile mutation authority remains process-global infrastructure and
must not be inferred for an explicit root or a non-active Profile.

## Intake provenance and durability

The public method records one `python-api` / `exact-memory-sequence-v1` Source
with a canonical JSON representation of the exact ordered sequence. The
checkpoint stores the same contents, created UIDs, Source hash/record, and
Grant audit metadata when applicable. Add has no provider, semantic cache,
hidden receipt, or saved review session.

Successful return means every requested Memory is present in order and one
checkpoint was published. Validation and target lookup failures publish
nothing. Context replacement or concurrent content changes fail through the
Store's UID/digest CAS rather than overwriting the newer Context.

## Stable errors

Public callers catch `AddError` or a bounded category:

- `AddInputError` for invalid caller values or blank batches;
- `AddContextError` for a missing target;
- `AddAuthorityError` for Profile or CREATE Grant failures;
- `AddConflictError` for target identity/digest races;
- `AddStorageError` for local I/O; and
- `AddExecutionError` for an authorized run that cannot produce a complete
  typed receipt.

Client construction retains the existing `QueryConfigurationError` behavior
for compatibility with the first `MemCommitClient` release. Renaming that
client-wide category is a separate API-version decision.

## Verification and non-goals

Focused tests prove local multiline/duplicate/order preservation, one
checkpoint, relative target resolution, validation before Store creation,
active CREATE-granted mutation, explicit-root and non-active-Profile isolation,
typed conflicts/storage failures, and root-package export identity.

This boundary does not add async cancellation, dry-run planning, caller-chosen
provenance, idempotency keys, resumable drafts, an agent schema, or an MCP
host. An agent adapter may project a versioned request onto this exact method;
it must not use CLI intake modes or reconstruct authority policy.

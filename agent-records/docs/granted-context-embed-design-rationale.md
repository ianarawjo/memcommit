# Grant-backed Context Embed

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Status

Implemented for explicit CLI and the shared Embed TUI. All three Study tasks'
ordinary READ source grants now include `EMBED`; QUERY-only and SHARE-only
routes do not. The representative 180×52 color-PTY path is retained under
[`screenshots/mem-granted-embed-20260814/`](screenshots/mem-granted-embed-20260814/README.md).

## Motivating boundary

READ answers whether a caller may inspect a Context now. Embedding is a
different downstream use: it persists a relationship from an owned Context to
authority-owned material and causes later recursive operations to consult that
material. Treating READ as implicit permission would prevent an authority from
allowing inspection while declining this durable use.

`EMBED` is therefore explicit and depends on `READ`. It does not imply DERIVE,
COMBINE, EXPORT, mutation, or acceptance of derived work. A narrower nested
Grant remains effective: a QUERY-only override below a READ + EMBED parent is
visible for orientation but cannot be selected or linked.

## Command and target contract

```text
mem embed GRANTED_CHILD --into OWNED_LOCAL_TARGET [--before ITEM | --after ITEM]
```

The Child resolves through the operation-neutral authority access boundary
with required permission `EMBED`. The target must exist in the active local
Store. Granting Embed into an authority-owned target is intentionally excluded
from this version because it would combine a persistent cross-Profile source
relationship with remote mutation authority and a second Store's restoration
history.

The TUI uses two catalogs. Child rows contain local names and all visible Grant
routes, annotated with their actual permissions; only local names and effective
EMBED grants are selectable. Into rows contain only owned local names. This
makes source authority visible without allowing a granted row to leak into the
target namespace.

## Persisted link schema

A local Child continues to serialize as `context_ref`. A granted Child
serializes as `granted_context_ref` containing only:

- the public and authority Context names and exact Context UID;
- authority and grantee Profile UIDs;
- attachment Context name and UID;
- Grant UID and its creation-time revision;
- resource name and UID.

No authority Memory content, query-only content, provider route, or cached
projection is stored in the target checkpoint. The Context UID remains the
direct-item identity so existing ordering, duplicate detection, removal,
branching, undo, and redo mechanics keep one relationship slot.

## Creation and traversal safety

Review freezes the Child's raw authority record digest, target digest, and
exact insertion neighbors. Apply holds the Grant registry snapshot lock and
the authority Context source lock through local target compare-and-set. Grant
revocation, permission removal, identity replacement, target drift, or source
record drift publishes no partial link.

Recursive load reauthorizes every `granted_context_ref`. It requires the same
active grantee, Grant UID, authority/resource/attachment identities, exact
authority Context binding, and current effective EMBED permission. A later
Grant revision may remain valid when all those identities and EMBED authority
survive; the live relationship should not break merely because another
permission was added.

If the embedded root binding is revoked or stale, recursive load fails closed.
Within an otherwise valid granted root, every effective nested override must
also retain `READ + EMBED`; an override that no longer permits traversal is
omitted from that live projection rather than inheriting the parent's broader
Grant. Direct load retains every opaque typed pointer, so either case never
silently deletes durable topology or shifts target order. Direct local edits
can continue and must serialize those pointers unchanged. Removal remains an
explicit target-side operation.

## Alternatives and limits

- Copying the granted Context into the target was rejected because it would
  create stale hidden content, bypass future revocation, and make provenance
  ambiguous.
- Storing an ordinary `context_ref` was rejected because same-Store lookup
  cannot identify or reauthorize a cross-Profile resource.
- Binding permanently to the creation revision was rejected. Revision is audit
  evidence, while current Grant identity, scope, and permission determine live
  authorization.
- Multiple public Grant aliases to the same authority Context cannot coexist as
  distinct direct items in one target because Context UID remains the item key.
  A second Embed resolving to the same Context UID is rejected before Apply and
  must never replace the existing link or create a checkpoint. Supporting
  alias-distinct relationships would require a wrapper item model and a
  deliberate traversal identity contract.
- Granted targets, QUERY-only embedding, cached content, and provider-mediated
  dereference are non-goals of this version.

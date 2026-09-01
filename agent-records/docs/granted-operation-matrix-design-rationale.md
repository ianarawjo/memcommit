# Granted operation matrix and artifact boundary

## Ownership boundary

Grant resolution, frozen bindings, registry locking, and readable projections
are owned by
`memcommit.application.context_access.access`. The resolved
value says which local or authority Store and exact Context a public name
denotes; it does not decide what an operation intends to do.

`memcommit.application.authorization.context_use` owns that second decision.
It authorizes `QUERY`, `CREATE`, `READ`, `UPDATE`, or `DELETE` against the
resolved `ContextAccess`. This separation keeps public-name resolution out of
operations while preventing resolution itself from silently granting a use.
Registry persistence and its compatibility schema remain under the Profile
operation until their persistence boundary is separated independently.

## Current operation contract

| Surface | Required Context use | Durable behavior |
|---|---|---|
| switch picker, ls, show, status, summarize | `READ` | Read-only public projection or output |
| find and quality discovery | `READ` | Current readable projection; query-only overrides excluded |
| query | `QUERY` (or stronger `READ`) | Mediated answer; query-only Source content is not exposed |
| add | `CREATE` | Direct Memory and checkpoint in the exact Target |
| edit | `UPDATE` | Direct Memory change and checkpoint |
| remove | `DELETE` | Direct item removal and checkpoint |
| chunk | `CREATE + DELETE` | Replacement UIDs saved atomically in one Context |
| clear | `DELETE` | Direct items removed in one Context save |
| forget | actual `UPDATE` and/or `DELETE` effects | One exact Target save |
| embed | Source `READ`; local placement | Live relationship; Source reauthorized on traversal |
| copy, compare, fit, search materialization, reference | Source `READ`; local Target ownership | Operation-owned local value or artifact contract |
| merge, meld, impact, update, resolve | Source `READ`; exact Target `CREATE`/`UPDATE`/`DELETE` effects | One locked Target publication with operation-specific review and rollback |
| share endpoint | separate `SHARE` capability | Reviewed receiver-owned delivery unit |

Every granted mutation revalidates the exact Grant revision, grantee and
authority Profile identities, attachment, public/resource mapping, and
required Context uses while the registry lock remains held through the write.

## Deliberate boundaries

- A narrower query-only Grant is never converted into readable evidence by a
  recursive parent operation. `READ` can answer a query; `QUERY` cannot open
  raw Memory content.
- Search uses only the frozen readable projection. Generic checkpoint
  browsing, Log, and Revert do not gain authority history access from `READ`.
- Context lifecycle and pointer operations do not treat an authority Context
  as participant-owned topology. The five uses govern direct content in an
  existing Context, not rename, branch, or Context deletion.
- Creating a result in a local Target needs no source-side export decision:
  the active Profile owns the Target. A granted Target must authorize every
  actual create, update, or delete effect.
- One operation may read several authorities, but current publication still
  writes at most one authority Store. A future multi-authority write needs a
  durable cross-store transaction journal and recovery protocol.
- `EMBED` remains a relationship/traversal mode. It is not a Grant permission,
  and following a granted live link continues to revalidate `READ`.
- Historical grant-bound analysis records remain compatible. New analyses use
  their operation's normal retained artifact contract rather than negotiating
  Grant-specific save permissions.

## Non-goal

The CLI cannot prevent a person from retyping or photographing `READ`-visible
text. The authorization model therefore avoids claiming control over derived
thought or retention and concentrates on mediated query disclosure, raw
content access, exact mutation effects, and atomic publication boundaries.

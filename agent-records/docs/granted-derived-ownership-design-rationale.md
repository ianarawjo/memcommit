# Context-use authorization for granted Contexts

## Decision

A Grant authorizes uses of an existing Context through one small vocabulary:

| Context use | Meaning |
|---|---|
| `QUERY` | Ask through the mediated query interface without disclosing raw Memory content. |
| `CREATE` | Add a direct Memory to the existing Context. |
| `READ` | Read the admitted Memory content and use it as operation input. |
| `UPDATE` | Change a direct Memory in the existing Context. |
| `DELETE` | Remove a direct item from the existing Context. |

`READ` also authorizes `QUERY`, because a caller that can already observe the
content may ask a question about it. `QUERY` does not imply `READ`. Grant
authoring requires `READ` alongside `CREATE`, `UPDATE`, or `DELETE`, while the
three mutation permissions remain independent of one another.

`SHARE` is not an ordinary Context use. It remains a separate delivery-endpoint
capability: it accepts one reviewed payload but does not expose the receiver's
Context for reading or general mutation.

The canonical application decision lives in
`memcommit.application.authorization.context_use`. A caller first resolves a
`ContextAccess`, then asks `authorize_context_use` for the exact use or uses its
operation will perform. Local Contexts pass because the active Profile owns
them; granted Contexts must carry the required permission.

## Why the derived-use vocabulary was removed

The earlier model tried to distinguish `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`,
`ACCEPT_DERIVED`, `SAVE_BOUND_ANALYSIS`, and `SAVE_ANALYSIS`. That distinction
suggested an enforcement boundary the local prototype cannot maintain. Once
`READ` exposes ordinary Memory content to the process and person, Mem cannot
reliably distinguish thinking, combining, transforming, retaining, or manually
transcribing that visible information. Requiring separate flags at selected
command routes therefore produced uneven command behavior without providing a
durable security guarantee.

The replacement asks only questions the system can enforce:

- may this operation obtain the Source content (`READ`) or only a mediated
  answer (`QUERY`)?
- may it create, update, or delete direct state in this granted Context?
- if a result is written locally, does the active Profile own that Target?
- if a result is written into a granted Target, which concrete mutation uses
  does that Target Grant allow?

A semantic operation may use any explicitly resolved readable Source. Mixing
several readable Sources requires no extra `COMBINE` flag. Creating a local
artifact requires no source-side `EXPORT` or target-side `ACCEPT_DERIVED` flag;
the local Profile owns that destination. Creating or changing an authority
Target still requires its exact `CREATE`, `UPDATE`, or `DELETE` permission and
the normal frozen-binding, lock, digest, and rollback checks.

## Embed, Reference, and Copy boundaries

`EMBED` is now a relationship shape, not a permission. Creating a live Embed
from a granted Source requires `READ`; recursively following the link
reauthorizes the same exact Grant and Source binding. Revocation therefore
closes the live projection while leaving the opaque relationship available for
repair or removal.

Copy may materialize a fresh local Memory from a readable granted Source.
Reference remains a frozen local snapshot where that operation supports the
Source; it does not pretend to be a live authority pointer. Granted Move is
still unsupported because it would delete authority-owned state and write a
different store as one transaction. The supported sequence is Copy followed by
an ordinary local Move.

These ownership and transaction boundaries are independent from the retired
derived-use flags. A multi-authority write still requires a durable cross-store
transaction design; simplifying permission vocabulary does not make that
publication atomic.

## Analysis and retained artifacts

Provider-backed Compare, Find, Meld, Update, and similar operations may consume
readable granted Sources under `READ`. A newly stored analysis uses the
operation's ordinary artifact contract rather than a Grant-specific
`SAVE_BOUND_ANALYSIS`/`SAVE_ANALYSIS` negotiation. New peer-relation analysis is
therefore retained in the active Profile. Historical records that already say
`GRANT_BOUND` remain readable and continue to revalidate their stored bindings;
new code does not author that mode.

Query-only routes remain narrower: they may return the operation's mediated
answer, but they are never admitted to ordinary Memory loading or to semantic
operations that require raw Source content.

## Compatibility boundary

New Grant create and update requests reject the retired permission names.
Registry and saved-binding readers accept the historical names only as a
migration boundary, discard them, and preserve the still-valid Context uses.
Legacy `SESSION_LOG` is normalized to `QUERY`. Re-saving a migrated Grant emits
only the canonical Context-use vocabulary plus the separate `SHARE` endpoint
capability.

This asymmetric compatibility is intentional: old data remains loadable, but
new callers cannot keep extending the obsolete policy model.

## Limitation

This remains an application-level research boundary, not operating-system
isolation or digital-rights management. The same OS user can inspect managed
Profile files, and Mem cannot constrain what a person does after receiving
readable text. The enforceable promise is narrower and explicit: query-only
content is not disclosed as Memory content, granted mutation is checked at the
exact Target, and Grant bindings are revalidated across publication races.

# Granted operation matrix and artifact boundary

## Problem

A granted Context should behave like an ordinary Context wherever its grant
authorizes the actual effect. Command parity cannot mean bypassing the grant by
persisting authority-owned source text in an unrelated participant artifact,
nor can a friendly command name stand in for the effects it eventually writes.

## Implemented current-state contract

| Surface | Required authority | Durable behavior |
|---|---|---|
| switch, ls, show, status, summarize | READ | Public virtual pointer or read-only output |
| find, find-duplicates, find-ambiguities, find-conflicts | READ | Current projection only; QUERY-only overrides excluded |
| query | QUERY | Provider-mediated result; SESSION_LOG separately controls saved query sessions |
| add | CREATE | Authority Memory and checkpoint |
| edit | UPDATE | Authority Memory and checkpoint |
| remove | DELETE | Authority Memory and checkpoint |
| chunk | CREATE + DELETE | Replacement UIDs saved atomically in one Context |
| clear | DELETE | Direct items removed in one Context save |
| forget | UPDATE and/or DELETE from accepted proposal | One authority Context save |
| integrate | CREATE, UPDATE, and/or DELETE from accepted proposal | One authority Context save |
| merge | source READ + DERIVE; EXPORT across domains; target CREATE + ACCEPT_DERIVED | Cross-Profile transfer copies direct Memory values only |
| compare | READ + DERIVE; COMBINE across domains; common SAVE mode | Exact grant-bound or retained artifact, otherwise process-local |
| meld | Compare save authority + source EXPORT; local target | Imports the exact ordered Compare ledger into a target-bound review session |
| impact | READ + source DERIVE/EXPORT + target ACCEPT_DERIVED | Schema 5 can bind granted source and target together |
| update | impact transfer authority + target mutation effects | Local or granted target application with exact bindings, receipts, and rollback |

Every granted mutation revalidates the exact grant revision, grantee and
authority Profile identities, attachment, public/resource mapping, and required
permission set while the registry lock remains held through the write.

## Deliberate boundaries

- A more-specific QUERY-only grant is never converted into READ evidence by a
  recursive parent operation.
- Temporal Find, generic checkpoint browsing, log, and revert do not use a READ
  grant because authority checkpoint history is a separate capability that the
  grant schema does not expose.
- Context lifecycle and pointer operations (`init`, `branch`, Context `delete`,
  Context `rename`, `embed`, and `reference`) do not treat an authority Context
  as participant-owned topology. A cross-Profile merge copies values rather
  than persisting authority-local Context or Memory-reference identities.
- An Update may read one granted authority and mutate a distinct granted target
  when the source grants DERIVE + EXPORT and the target grants ACCEPT_DERIVED
  plus every planned mutation permission. It locks both exact source and target
  scopes, but writes and rolls back only the target authority store. A future
  operation that writes more than one authority still needs a cross-store
  transaction journal.
- Granted Compare uses a distinct artifact containing the exact analysis and
  frozen source bindings. Grant-bound artifacts require live revalidation;
  retained artifacts survive revocation because permanent retention was
  authorized by every source when saved.
- `atomize`, `review`, and `translate` currently use durable artifacts
  containing source or derived text and local Context identities. Grant parity
  for these commands is deferred until each artifact has a redacted form and a
  live grant revalidation path. Simply pointing their existing local stores at
  an authority Profile would either leak text into the participant Profile or
  mutate authority-owned workflow state without an explicit permission model.

## Non-goal

The CLI cannot prevent a participant from manually retyping or photographing
READ-visible text. The enforceable boundary is that Mem itself does not create
hidden, durable authority copies or perform effects outside the grant contract.

# Granted operation matrix and artifact boundary

## Ownership boundary

Grant access resolution, frozen binding, authorization locking, and bounded
READ projection are owned by `memcommit.application.capabilities.authority.access`.  They are shared
application infrastructure, not CLI behavior: command, runtime, evaluation,
and study adapters import that owner directly.  The former
`memcommit.adapters.console.commands.granted_context` module was removed rather than retained
as a compatibility facade so a terminal-facing package cannot remain the
dependency root for non-terminal application slices.

Profile-registry persistence and its serialized compatibility schema remain in
`profile_config` and `profiles` for this behavior-preserving move.  Separating
those persistence responsibilities is independent from locating the shared
authorization boundary and must preserve existing registry and saved-artifact
formats when undertaken.

## Problem

A granted Context should behave like an ordinary Context wherever its grant
authorizes the actual effect. Command parity cannot mean bypassing the grant by
persisting authority-owned source text in an unrelated participant artifact,
nor can a friendly command name stand in for the effects it eventually writes.

## Implemented current-state contract

| Surface | Required authority | Durable behavior |
|---|---|---|
| switch, ls, show, status, summarize | READ | Public virtual pointer or read-only output |
| find, dedun discovery, find-ambiguities, find-conflicts | READ | Current projection only; QUERY-only overrides excluded |
| query | QUERY | One process-local provider-mediated result; no transcript retention |
| add | CREATE | Authority Memory and checkpoint |
| edit | UPDATE | Authority Memory and checkpoint |
| remove | DELETE | Authority Memory and checkpoint |
| chunk | CREATE + DELETE | Replacement UIDs saved atomically in one Context |
| clear | DELETE | Direct items removed in one Context save |
| forget | UPDATE and/or DELETE from accepted proposal | One authority Context save |
| merge | source READ + DERIVE; EXPORT across domains; target CREATE + ACCEPT_DERIVED | Cross-Profile transfer copies direct Memory values only |
| compare | READ + DERIVE; COMBINE across domains; common SAVE mode | Exact grant-bound or retained artifact, otherwise process-local |
| meld | Symmetric: Compare save authority + source EXPORT, local result. Directional: READ/DERIVE, COMBINE/EXPORT and ACCEPT_DERIVED across domains, plus baseline CREATE/UPDATE effects | Symmetric imports an ordered Compare ledger; directional freezes both endpoint Grants and updates a granted baseline in its authority Profile with rollback |
| impact | READ + source DERIVE/EXPORT + target ACCEPT_DERIVED | Schema 5 can bind granted source and target together |
| update | impact transfer authority + target mutation effects | Local or granted target application with exact bindings, receipts, and rollback |

Every granted mutation revalidates the exact grant revision, grantee and
authority Profile identities, attachment, public/resource mapping, and required
permission set while the registry lock remains held through the write.

## Deliberate boundaries

- A more-specific QUERY-only grant is never converted into READ evidence by a
  recursive parent operation.
- Search uses only the current READ projection. Generic checkpoint browsing,
  Log, and Revert do not use a READ grant because authority checkpoint history
  is a separate capability that the grant schema does not expose.
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
- Directional Meld follows the same ownership boundary for its single
  BASELINE. Grant INCOMING is locked and revalidated as a read-only source;
  Grant BASELINE is revalidated for the exact ADD/EDIT effects and mutated in
  its authority store. Both endpoints may belong to the same exact Grant
  domain, in which case no artificial export boundary is introduced.
- The retired `integrate` command is not a granted mutation route. Historical
  checkpoints remain readable under their original command identity, but new
  semantic ingestion must use the reviewed directional Meld or Update paths.
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

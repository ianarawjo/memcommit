# `mem share` design rationale

## Problem

Task 3 ends with one consequential disclosure action. A success message that
does not change receiver state cannot distinguish a reviewed draft from an
actual study delivery. At the same time, a sender must not gain a general path
for writing arbitrary Contexts into another Profile.

## Initial command contract

```text
mem share [SEVER_OUTPUT] --to government/healthcare-agent
```

The source defaults to the current Context. This first implementation accepts
only a nonempty, unchanged Context whose newest checkpoint is its applied
`sever` creation checkpoint. Every direct item must be an ordinary Memory.
References, embedded Contexts, arbitrary local Contexts, excluded Sever
candidates, and Sever rationale are not transmitted.

The complete ordered Memory batch is one consent unit. A successful command
creates an ordinary receiver-owned Context at:

```text
RECEIVER_ROOT/received-shares/SHARE_UID
```

Its direct Memories contain the transmitted text. Its automatic
`share-receive` checkpoint records the sender Profile identity, exact endpoint
grant and revision, source Context identity and digest, source-to-received
Memory UID mapping, and consent-unit digest.

## Endpoint authority

`--to` is not a Profile name or writable filesystem/Context path. It resolves
exactly one `SHARE` authority grant whose grantee is the active sender Profile.
The grant's public name is the endpoint name and its authority resource root is
the receiver-owned placement root. Resolution verifies the grantee attachment,
receiver Profile, receiver Context UID, and frozen root binding while holding
the registry grant lock.

Task 3 publishes `government/healthcare-agent` this way. Public healthcare
guidance and query-only Q&A remain separate grants. `SHARE` grants do not imply
`READ`, so the participant can deliver without browsing the receiver Profile
or its prior deliveries.

## Freshness, commit boundary, and retry

The registry lock freezes Profile and grant identities through delivery. The
source Context write lock is held from the final UID/digest and Sever receipt
recheck until the receiver Context commit completes. The receiver uses its
normal require-new Context and checkpoint boundary.

The share UID is deterministic over the endpoint grant, sender Profile, source
identity/digest, and consent digest. Retrying the same reviewed unit validates
the existing receiver Context and `share-receive` receipt, then returns success
without a duplicate. A collision with different data or an invalid receipt
fails closed.

## Alternatives considered

- **Treat the receiver as another readable grant view:** rejected because a
  view authorizes observation, not delivery, and would expose receiver state.
- **Let `--to` name a Profile or ordinary Context directly:** rejected because
  it turns a task endpoint into general cross-Profile write access.
- **Store only a sender-side receipt:** rejected because it still simulates
  delivery without producing receiver-owned Memories.
- **Move or reference the Sever output:** rejected because later sender edits,
  deletion, or permission changes must not rewrite what was received.

## Boundary and current limitations

This is a real persistent transfer between local research Profiles, not an
authenticated network transfer to an operating government system. The stores
remain under one OS user and do not provide production isolation.

The first slice has no interactive review screen, sender-side receipt artifact,
receiver acknowledgement, recall, or multi-endpoint routing. It intentionally
supports only exact applied Sever output. Receiver creation is the commit
point; a later sender-side audit index should be recoverable secondary state.

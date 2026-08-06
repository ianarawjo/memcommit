# `mem share` design rationale

## Problem and command

`mem share` is the consequential cross-Profile delivery boundary. It is
independent of how its source Context was created: a Source may be authored,
updated, melded, severed, or produced by another ordinary local workflow.

```text
mem share [SOURCE_CONTEXT] --to ENDPOINT
```

Complete operands use the direct command path. In a TTY, missing operands open
ordinary-Context and endpoint pickers, freeze the selection, and show the
Share viewer before receiver state changes. Query-only sources are never
opened or offered.

## Selection and send

The source picker lists nonempty ordinary Contexts whose direct items are all
ordinary Memories. It does not require a particular creator command or
checkpoint. This deliberately decouples Share authorization from Sever or any
other semantic transformation.

The source picker shows Context names only; it does not expand every candidate's
Memories. After selection, the viewer has three regions: `CONTEXT` shows the
selected name and endpoint, `MEMORIES` shows only that Context's direct
Memories, and `ACTION` contains the one `SEND CONTEXT` action. It has no
provider turn, semantic options, or durable Share session. If no source or
endpoint exists, the same surface opens read-only with `SEND UNAVAILABLE`.

The viewer freezes the canonical Source name and UID, Source digest, ordered
Memory contents, consent digest, endpoint Grant UID and revision, receiver
identity, and deterministic placement. Send revalidates the complete frozen
projection under the registry and Context locks. Any Source or endpoint change
requires reopening Share and reviewing a fresh snapshot.

References and embedded Contexts are rejected because Share must send exactly
the direct Memories shown in the viewer. Empty Contexts are not eligible.

## Delivery and authority

`--to` resolves one exact `SHARE` authority Grant whose grantee is the active
sender Profile. It is not a general Profile or filesystem path. Resolution
checks the grantee attachment, receiver Profile, receiver Context UID, and
frozen resource root while holding the registry Grant lock. `SHARE` does not
imply receiver `READ` access.

The ordered Memory batch is one frozen Context snapshot. Delivery creates a
receiver-owned ordinary Context at:

```text
RECEIVER_ROOT/received-shares/SHARE_UID
```

Its direct Memories contain the selected text. The `share-receive` checkpoint
records sender identity, endpoint Grant and revision, Source identity and
digest, source-to-received UID mapping, and consent digest.

The Share UID is deterministic over endpoint, sender, Source identity/digest,
and consent digest. Retrying the same unit validates and reuses the receiver
Context; a collision with different data fails closed.

## Alternatives and limitations

- Requiring a Sever checkpoint was rejected because it incorrectly made a
  content-forgetting transformation the authority boundary for sharing.
  Share's own exact preview and approval are the relevant boundary.
- Treating the receiver as a readable Grant view was rejected because viewing
  does not authorize delivery and would expose receiver state.
- Letting `--to` name an arbitrary Profile or Context was rejected because that
  would create general cross-Profile write authority.
- Moving or referencing the Source was rejected because later sender edits or
  deletion must not rewrite the receiver-owned copy.

This remains a local research-profile transfer, not an authenticated network
transfer. There is no sender-side receipt artifact, receiver acknowledgement,
recall, or multi-endpoint routing yet.

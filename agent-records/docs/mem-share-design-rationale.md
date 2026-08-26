# `mem share` design rationale

## Problem and command

`mem share` is the consequential cross-Profile delivery boundary. It is
independent of how its source Context was created: a Source may be authored,
updated, melded, severed, or produced by another ordinary local workflow.

```text
mem share [SOURCE_CONTEXT] [-d | -r] --to ENDPOINT
```

Complete operands use the direct command path. In a TTY, missing operands open
ordinary-Context and endpoint pickers, freeze the selection, and show the
Share viewer before receiver state changes. Query-only sources are never
opened or offered.

Omission and `-d/--direct` select the exact Source Context. `-r/--recursive`
selects that Context plus every ordinary local lexical descendant. Share does
not follow embedded Context edges: an embed is a relationship to separately
owned material, whereas recursive Share is an explicit namespace bundle. The
two flags are mutually exclusive so the command line records one unambiguous
disclosure range.

## Selection and send

The source picker lists ordinary Context roots whose requested range contains
at least one Memory and whose direct items are all ordinary Memories. A direct
Source must itself be nonempty. A recursive Source may use empty structural
Context members, including an empty root, provided the complete bundle has at
least one Memory. It does not require a particular creator command or
checkpoint. This deliberately decouples Share authorization from Sever or any
other semantic transformation.

The source picker shows Context names only; it does not expand every candidate's
Memories. After selection, the viewer has four regions in disclosure order.
Direct Share keeps its `FROM · CONTEXT` projection, while recursive Share uses a
compact `FROM · CONTEXTS` roster showing the root summary, every included
canonical Context name, and its direct-Memory count. `TO · SHARE ENDPOINT`
shows the selected Grant-backed endpoint and exposes Browse. `MEMORIES` shows
every disclosed direct Memory with its complete durable Memory UID and, for a
bundle, its owning Context. `APPLY` shows the exact explicit `mem share` command
plus `[ PRESS ENTER TO APPLY ]`. It has no provider turn, semantic options, or
durable Share session. If no complete plan exists, the same four-surface shape
opens read-only with unavailable endpoint and Apply projections.

Each recursive Context consumes exactly one unboxed row:

```text
ROOT · practice · 4 CONTEXTS · 3 MEMORIES
C1 · practice              · 1 Memory
C2 · practice/appointments · 1 Memory
C3 · practice/empty-lane   · 0 Memories
C4 · practice/medication   · 1 Memory
```

The focused row alone receives the shared blue focus treatment. Full names and
zero-Memory members remain visible because an aggregate-only summary would
hide part of the consent unit. Per-Context cards, repeated count lines, and
blank separators were rejected because they consumed about three terminal
rows per member and made even a four-Context bundle require scrolling. A
collapsible tree was also rejected: it would save space by concealing exactly
which members will be sent.

The endpoint is not arbitrary writable text: Browse shows only the complete
currently available `SHARE` endpoint catalog. Enter on `TO` leaves the frozen
viewer for that picker. Cancelling returns to the same endpoint, while choosing
another endpoint re-prepares the complete Source scope because endpoint Grant
identity participates in the consent digest, Share UID, and receiver placement.
The viewer then reopens with `TO` focused and both its visible endpoint and exact
Apply command updated from the same fresh preview.

These four regions declare the shared Surface topology
`FROM → TO → MEMORIES → APPLY`. Tab and Shift-Tab wrap without resetting the
Viewer section, selected endpoint, or Memory cursor. Up and Down first move
within the current region, then cross a real top or bottom boundary without
wrapping; vertical entry selects the nearest Source section or Memory row.
Enter opens Browse in `TO`, applies only the displayed exact command in `APPLY`,
and remains inert in `FROM` and `MEMORIES`. Direct previews spell `--direct`
and recursive previews spell `--recursive`, even where the CLI would accept an
omitted direct flag, so the reviewed disclosure range is explicit. Escape and
Backspace use the same read-only close path, while Q and Ctrl-C remain immediate
close aliases. The unavailable projection uses the same topology but gives its
`TO` and `APPLY` Surfaces no activation capability, so no navigation or Enter
sequence can manufacture a send action.

The shared Surface controller owns only focus and key routing. Share continues
to own Source and endpoint eligibility, the frozen preview, the exact send
meaning, authority revalidation, and delivery. This separation keeps keyboard
behavior consistent with other workbenches without turning a presentation
component into a disclosure boundary.

The viewer freezes the canonical Source root, direct/recursive range, complete
ordered Context membership, every Context name/UID/digest, ordered Memory
contents, consent digest, endpoint Grant UID and revision, receiver identity,
and deterministic placement. Send revalidates the complete frozen projection
under the registry, namespace-graph, and Context locks. A recursive Send holds
an exclusive Source graph lock from final membership validation through
receiver publication, so a new child cannot enter the bundle after review. Any
Source, membership, or range change requires reopening Share and reviewing a
fresh snapshot. An endpoint change through the viewer's own Browse path also
creates a fresh preview and requires reviewing its updated `TO` and `APPLY`
surfaces before Apply.

References and embedded Contexts are rejected because Share must send exactly
the direct Memories shown in the viewer. They are not silently traversed or
converted into owned receiver data.

## Delivery and authority

`--to` resolves one exact `SHARE` authority Grant whose grantee is the active
sender Profile. It is not a general Profile or filesystem path. Resolution
checks the grantee attachment, receiver Profile, receiver Context UID, and
frozen resource root while holding the registry Grant lock. `SHARE` does not
imply receiver `READ` access.

The ordered direct Context or recursive Context batch is one frozen consent
unit. Delivery creates a receiver-owned ordinary Context root at:

```text
RECEIVER_ROOT/received-shares/SHARE_UID
```

Direct Share stores the exact Source Memories there. Recursive Share preserves
every lexical suffix below that root, so `SOURCE/child/grandchild` becomes
`RECEIVER_ROOT/received-shares/SHARE_UID/child/grandchild`. Every member is an
ordinary receiver-owned Context. Its `share-receive` checkpoint records sender
identity, endpoint Grant and revision, Source root and member identities and
digests, the complete bundle manifest, source-to-received UID mappings, and
the shared consent digest.

The Share UID is deterministic over endpoint, sender, Source identity/digest,
range version, and consent digest. Version-1 direct digest and UID construction
remain byte-compatible so an exact unit delivered before recursive support is
still idempotent. Retrying the same unit validates and reuses the complete
receiver Context set; a partial set or collision with different data fails
closed.

Receiver publication uses one command lock and one complete destination lock
set. Every member is preflighted before the first creation, and an exception
rolls back members created earlier in the batch. This research prototype
therefore provides exception atomicity for a recursive Share, not a durable
cross-store transaction journal that can recover from a process or machine
crash between Context-file replacements.

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
- Flattening descendants into one received Context was rejected because it
  erases the namespaced grouping the recursive option is meant to preserve and
  makes equal Memory text from different child Contexts indistinguishable.
- Following embedded Contexts under `-r` was rejected because lexical ownership
  and graph reach are independent axes. A referenced or embedded Context must
  be selected and reviewed as its own Share root.
- Keeping Share-authored Tab and arrow handlers was rejected after the common
  Surface contract existed. That duplicate path clamped Up/Down inside each
  frame and maintained a second Memory cursor beside the shared workbench
  navigation state. Adapting the three existing regions to `FocusSurface`
  preserves Share semantics while removing the divergent mechanics.

This remains a local research-profile transfer, not an authenticated network
transfer. There is no sender-side receipt artifact, receiver acknowledgement,
recall, multi-endpoint routing, or durable cross-store crash-recovery journal
yet.

## Verification record

- `tests/test_share.py` covers direct version-1 compatibility, recursive
  hierarchy preservation, empty structural members, idempotence, mutually
  exclusive range flags, reviewed-membership freshness, receiver rollback,
  interactive range propagation, and viewer projection.
- `agent-records/docs/screenshots/mem-share-recursive-20260822/` records the ordered real
  `180×52` color-PTY endpoint, review, approval, success, read-only
  verification, cancellation, and stale-membership failure states.

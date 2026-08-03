# Query session design rationale

## Decision

`mem query VIEW QUESTION` remains a one-shot, unsaved operation. A person may
explicitly name a durable chat-like transcript with `--session NAME`, but only
when the view's grant includes both `QUERY` and `SESSION_LOG`.

```bash
mem query campus-wiki/construction-details
mem query 'campus-wiki/construction-details#q-7d19c531f084' "What is this item about?"
mem query campus-wiki/construction-details "What is planned?"
mem query campus-wiki/construction-details "What depends on that?" --session campus-review
mem query --sessions
mem query --show-session campus-review
```

The session belongs to the active task Profile. It stores the questions and
answers that were already visible to the person, plus opaque binding and
freshness digests. It never stores the authority source, source entry
metadata, provider prompt, authentication material, or hidden provider state.

## Opaque Memory catalog

Omitting `QUESTION` from an authority-granted view opens its query flow as an
opaque Memory catalog. `QUERY` itself authorizes this catalog; it is not an
ordinary `LIST` or `READ` capability. Each admitted Memory is represented by
a per-grant opaque handle and a Flow Circular capsule. The renderer replaces
every source word with an equal-code-point-length dummy mask in memory, draws
that mask with the bundled Flow Circular TTF, and converts the four-pixel-high
raster to Unicode Braille cells. The source characters are never sent to the
font renderer or terminal. Copying terminal output therefore copies only
Braille pixels, never the source or dummy mask characters.

The catalog intentionally discloses the number and order of queryable
Memories, normalized word boundaries, and each word's Unicode-code-point
length. Runs of whitespace are collapsed to one ordinary space; punctuation
and every other non-space character contribute only to their word's length.
The handle is derived from the grant and Memory identities, so it remains
stable across ordering and content edits without exposing the authority
Memory UID. Recreating the grant changes the handle. A missing or nonmatching
handle fails closed.

Flow Circular is bundled unmodified from the Google Fonts distribution under
the SIL Open Font License 1.1, with its copyright and license alongside the
TTF. Pillow is the rasterization dependency. Terminal ANSI cannot select a
font for one span, so the Braille raster is the portable CLI representation of
the actual Flow Circular geometry; the terminal's own Braille glyph design can
slightly affect its final appearance.

Using `VIEW#HANDLE` with a question sends only that selected Memory to the
provider. The existing `VIEW QUESTION` form remains a whole-view query for
compatibility. Handles and placeholders are process-local projections: they
are not written into the grantee Context, grant registry, query transcript,
or clipboard metadata.

## Provider and replay contract

Every turn is still a fresh provider call. For a continued session, memcommit
reconstructs the dialogue from the saved visible Q/A and sends that replay
with the current question. This makes the referent of a short follow-up
auditable and portable instead of relying on a provider-side conversation the
local application cannot inspect.

Provider authentication occurs before authority Context content is loaded,
including when only the opaque catalog is requested.
The ephemeral source is serialized only from ordinary direct Memories whose
Context UID/name pairs occur in the query grant's frozen scope. A complete
root-bound translation catalog is required for a non-English query.

## Freshness and publication

A saved session binds to:

- grant UID, revision, and canonical grant digest;
- grantee and authority Profile UIDs;
- attachment and resource Context identities;
- public and requested view names;
- language; and
- the exact serialized source snapshot digest.

Changing the grant, source Memories, translation, language, or view makes the
old session stale. The person must choose a new session name rather than
silently continuing against different evidence. After the provider returns,
the command re-resolves the permission and source. Revocation or source drift
during inference prevents both transcript publication and answer display.
The registry grant lock remains held from that final check through transcript
publication and terminal disclosure, closing a revoke-after-check race.
Session append uses a record digest CAS so concurrent turns cannot overwrite
one another.

Files live under the task store's `query-sessions/` directory. The directory
and lock directory require mode `0700`, records and locks require `0600`, and
unsafe links, permissions, duplicate JSON keys, oversized records, invalid
names, or identity mismatches fail closed. Publication uses a same-directory
fsynced temporary file and atomic replacement.

## Why `SESSION_LOG` is separate

Permission to ask one question does not necessarily authorize durable
retention. `SESSION_LOG` makes that additional data-lifecycle choice explicit
and depends on `QUERY`. Revoking the authority grant blocks new turns, while
an already stored task-owned transcript remains locally inspectable because
it contains only material previously disclosed to that task.

## Alternatives considered

- **Save every query automatically:** rejected because it changes the legacy
  non-retention contract and creates logs without an explicit user choice.
- **Reuse a hidden provider session:** rejected because behavior would depend
  on state that cannot be reviewed, replayed, or migrated to MCP.
- **Store source snapshots with the transcript:** rejected because it would
  turn query authority into read/copy authority and retain concealed data in
  the task Profile.
- **Render the real source directly in Flow Circular:** rejected because copy,
  accessibility, terminal history, and logs would still contain the source
  characters. The selected renderer sends only equal-length dummy masks to
  Flow Circular and emits only raster cells.
- **Add a separate `LIST` permission:** rejected because the catalog is part
  of selecting the object of a query and never lists source content or
  authority identities.
- **Continue after source changes:** rejected for this study because a single
  transcript would then cite multiple unstated evidence snapshots.

## Limitations

The current surface lists and shows sessions but does not yet rename, export,
or delete them. The provider can still answer too broadly, and the local
research boundary is not OS-level confidentiality. A future MCP provider may
replace source loading while retaining the same explicit transcript and
freshness contract.

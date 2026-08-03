# Query session design rationale

## Decision

`mem query VIEW QUESTION` remains a one-shot, unsaved operation. A person may
explicitly name a durable chat-like transcript with `--session NAME`, but only
when the view's grant includes both `QUERY` and `SESSION_LOG`.

```bash
mem query campus-wiki/construction-details "What is planned?"
mem query campus-wiki/construction-details "What depends on that?" --session campus-review
mem query --sessions
mem query --show-session campus-review
```

The session belongs to the active task Profile. It stores the questions and
answers that were already visible to the person, plus opaque binding and
freshness digests. It never stores the authority source, source entry
metadata, provider prompt, authentication material, or hidden provider state.

## Provider and replay contract

Every turn is still a fresh provider call. For a continued session, memcommit
reconstructs the dialogue from the saved visible Q/A and sends that replay
with the current question. This makes the referent of a short follow-up
auditable and portable instead of relying on a provider-side conversation the
local application cannot inspect.

Provider authentication occurs before authority Context content is loaded.
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
- **Continue after source changes:** rejected for this study because a single
  transcript would then cite multiple unstated evidence snapshots.

## Limitations

The current surface lists and shows sessions but does not yet rename, export,
or delete them. The provider can still answer too broadly, and the local
research boundary is not OS-level confidentiality. A future MCP provider may
replace source loading while retaining the same explicit transcript and
freshness contract.

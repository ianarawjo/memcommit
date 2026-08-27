# Profile authority grant design rationale

## Decision

Cross-Profile authority is expressed as a registry capability grant. Ordinary
source access remains a permissioned **view**, not a fork, merge, copy, or
embedded Context: source data stays physically owned by one switchable
authority Profile and a task Profile receives a public projection. A `SHARE`
grant is the deliberate asymmetric exception: its public name is a write-only
delivery endpoint and an approved consent unit becomes a receiver-owned copy.

```text
task Profile                         task-specific authority Profile
┌──────────────────────────┐        ┌───────────────────────────────┐
│ participant/task anchor  │        │ ordinary source Context tree  │
│   └── granted view ──────┼───────>│ stable Context UIDs           │
└──────────────────────────┘        └───────────────────────────────┘
           permissions + frozen exact scope
```

The source becomes fully editable through ordinary commands when the
authority Profile is selected. In the task Profile, `mem contexts`, `mem ls`,
and `mem show` expose only locally owned Contexts plus granted public views.
A view is deliberately not accepted by `mem switch`: switching changes the
current ordinary Context inside one Profile, whereas a grant is a capability
resolved for a command.

The registry control plane stores each grant's stable UUID and revision,
authority and grantee Profile UIDs, attachment Context UID and name, authority
root Context UID and name, public path, permissions, and a frozen allowlist of
exact authority Context UID/name pairs. Context data and checkpoints are not
copied into the registry or grantee store. `SHARE` payloads are written only to
the authority-owned receiver store; the registry remains capability metadata.

## Permission contract

Permissions are independent capabilities:

| Permission | Task-side operation |
| --- | --- |
| `READ` | list or show ordinary Memories admitted by the view |
| `CREATE` | add a direct Memory; requires `READ` |
| `UPDATE` | edit a direct Memory; `EDIT` is a CLI input alias; requires `READ` |
| `DELETE` | remove a direct item; requires `READ` |
| `QUERY` | ask a provider over an authorized Context-level View without receiving source text |
| `SHARE` | deliver one exactly reviewed ordinary Context or lexical subtree snapshot as a receiver-owned consent unit; grants no receiver read access |

These permissions currently govern direct items inside existing Contexts.
They do not delegate Context lifecycle operations such as `init`, `rename`,
or Context deletion. The authority owner can perform those operations after
switching to its Profile. This narrower interpretation avoids granting a
namespace rewrite when the study only needs Memory authoring.

Grant CRUD is separate from data CRUD:

```text
mem profile grant create AUTHORITY GRANTEE RESOURCE \
  --into ATTACHMENT --allow READ --recursive
mem profile grant list
mem profile grant update GRANT --allow READ --allow UPDATE
mem profile grant delete GRANT
```

Creation snapshots the currently admitted Context identities. New descendants
do not enter the view until `--refresh-scope` is explicitly applied. Revoking
a grant removes the view immediately and never deletes either Profile's data.

## Nested views and fail-closed precedence

A narrower public grant overrides a broader one by longest path. This is
required for Task 1: `campus-wiki` is readable and editable, while
`campus-wiki/construction-details` is query-only. Recursive listing filters
the narrower tree from the broader `READ` projection and renders only its
query link. `mem query VIEW` opens the Query workbench with that public View
selected, while `mem query VIEW QUESTION` asks over its complete authorized
frame without exposing ordinary Memory content. It never falls back to the
parent's permission when the narrower grant denies the requested operation.

Every operation validates the attachment Context and authority Context UIDs.
A mutation re-resolves the grant immediately before saving and requires the
same grant UID, revision, Profiles, and authority Context. It holds the
registry's grant lock until the authority-store save completes, so revocation
cannot race into the interval between authorization and publication. The
authority MemoryStore's normal digest CAS then protects the content snapshot.
A revoked or revised grant and a replaced Context therefore fail closed
instead of writing through stale authority.

## Study topology

The packaged Legacy scenario contains one task store, one separate authority
store, and Grant templates for each task. `mem init-study --scenario legacy`
builds and validates the six intermediate stores privately, composes one
participant Profile and one run-private authority Profile, and materializes
the templates as real registry Grants. No intermediate Profile is registered.

| Task | Task-owned data | Authority Profile and ordinary data | Granted views |
| --- | --- | --- | --- |
| 1 | `participant/construction-updates` | `task-1-campus-authority`: `campus-wiki`, including construction details | wiki `READ+CREATE+UPDATE+DELETE+QUERY`; nested details `QUERY` |
| 2 | `participant/proposal-workspace` | `task-2-proposal-authority`: `advisor1`, `advisor2`, submission guidelines | advisors `READ`; guidelines `QUERY` |
| 3 | `local/personal-memory`, `local/guardrails` | `task-3-healthcare-authority`: `remote/government/healthcare-agent/info-request/transmission-guidance`, `questions-and-answers` | healthcare agent `SHARE`; public transmission guidance `READ+DERIVE+COMBINE+EXPORT+SAVE_BOUND_ANALYSIS+SAVE_ANALYSIS`; questions-and-answers `QUERY` |

`task-1-campus-authority` is intentionally task-specific. A future shared
campus authority may be appropriate for a different experiment, but this
fixture's exact contents and permissions are part of Task 1's condition.
`QUERY` on the editable wiki and narrower details view is explicit so both can
answer one-shot questions without granting READ over the query-only override.
Query transcript retention is not an experimental condition. Every Profile's
command-attempt telemetry may retain a direct CLI command containing a
question, but it does not retain the answer or create a reopenable Query
transcript.

During private composition, authority material is temporarily namespaced below
`granted-memory/task-N`; the published authority Profile owns it below
`task-N`. The temporary store is deleted after the final pair is published and
is never a Grant endpoint.

When `mem init-study` omits its name in a TTY, the command stays in the ordinary
terminal transcript and opens a five-row inline TUI prefilled with the existing
`study-YYYYMMDDTHHMMSSZ-xxxxxxxx` default. It uses the same prompt-toolkit input
behavior as the other terminal workbenches without entering an alternate or
full-screen surface. A left-aligned `STUDY NAME` label sits above an untitled
rectangular edit field so the label cannot be mistaken for a centered border
choice. The cursor starts at the default's end. Enter validates
and uses the exact visible name; Escape creates nothing. An explicit positional
name bypasses the prompt, while non-TTY execution retains automatic naming so
scripts do not acquire an interactive dependency.

A successful `init-study` registry transaction selects the new participant
Profile as active, matching `mem init`'s create-and-enter behavior. The paired
`-granted-memory` authority Profile is never selected. Cancellation or any
failure before registry replacement publishes nothing and leaves the previously
active Profile unchanged. If replacement becomes visible but its durability
confirmation fails, the complete run remains registered and selected because
rolling back only the active pointer would expose a partial generation.

## Why registry grants

The grant is relationship metadata involving two Profiles, so it lives in
the same external, locked registry that selects Profiles. Keeping it outside
both MemoryStores prevents a branch, checkpoint, copy, or Context edit from
silently duplicating or escalating access. The registry can publish all
Profile and grant identities as one atomic generation. This control-plane
record is also a direct local analogue of a future MCP or internal-network
capability without pretending the local prototype already supplies remote
security.

## Alternatives considered

- **Fork or copy the authority tree into each task:** rejected because edits
  create divergent owners and require an undefined merge/publication model.
- **Store query-only data only in `query-sources/`:** retained for legacy
  fixtures, but rejected as the new authority model. The owner could not use
  normal Context CRUD, and read, edit, and query grants could not share one
  source identity.
- **Persist grant pointers inside task Contexts:** rejected because Context
  checkpoints, branches, and merges would copy capability-looking records.
- **Recursively include future descendants:** rejected because an authority
  author could accidentally disclose newly created material. Scope refresh is
  explicit.
- **Treat audience fixture metadata as ACL:** rejected. Audience labels remain
  study annotations and never grant runtime authority.

## Limitations

This is a local research permission boundary, not operating-system isolation.
The same OS user can read managed Profile files directly. Granted views do
not yet support Context lifecycle commands, `impact`, or `update` as a
cross-store target. A granted Memory mutation records its checkpoint and
grant audit metadata in the authority store; task-side `undo` does not span
stores, so recovery currently requires selecting the authority Profile.
Provider-backed `QUERY` remains the only supported way to open query-only
content from a task Profile. Production use should move the authority store
and enforcement to an authenticated MCP or internal service.

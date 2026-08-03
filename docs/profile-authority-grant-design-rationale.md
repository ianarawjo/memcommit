# Profile authority grant design rationale

## Decision

Cross-Profile access is a permissioned **view**, not a fork, merge, copy, or
embedded Context. Ordinary source data remains physically owned by one
switchable authority Profile. A task Profile receives a registry grant that
projects a public Context path into one existing task Context.

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
copied into the registry or grantee store.

## Permission contract

Permissions are independent capabilities:

| Permission | Task-side operation |
| --- | --- |
| `READ` | list or show ordinary Memories admitted by the view |
| `CREATE` | add a direct Memory; requires `READ` |
| `UPDATE` | edit a direct Memory; `EDIT` is a CLI input alias; requires `READ` |
| `DELETE` | remove a direct item; requires `READ` |
| `QUERY` | ask a provider about the admitted source without listing it |
| `SESSION_LOG` | retain and replay visible query Q/A; requires `QUERY` |

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
query link. It never falls back to the parent's permission when the narrower
grant denies the requested operation.

Every operation validates the attachment Context and authority Context UIDs.
A mutation re-resolves the grant immediately before saving and requires the
same grant UID, revision, Profiles, and authority Context. It holds the
registry's grant lock until the authority-store save completes, so revocation
cannot race into the interval between authorization and publication. The
authority MemoryStore's normal digest CAS then protects the content snapshot.
A revoked or revised grant and a replaced Context therefore fail closed
instead of writing through stale authority.

## Study topology

The generated study package for each task contains a task store, a separate
authority store, and grant templates. `mem profile import-study` validates all
six package stores and composes one editable `study-baseline` Profile. `mem
init-study` later snapshots that live source, allocates run-local Profile UIDs,
splits the task and `granted-memory` branches, binds grants, and publishes the
registry atomically.

| Task | Task-owned data | Authority Profile and ordinary data | Granted views |
| --- | --- | --- | --- |
| 1 | `participant/construction-updates` | `task-1-campus-authority`: `campus-wiki`, including construction details | wiki `READ+CREATE+UPDATE`; nested details `QUERY+SESSION_LOG` |
| 2 | `participant/proposal-workspace` | `task-2-proposal-authority`: `advisor1`, `advisor2`, submission guidelines | advisors `READ`; guidelines `QUERY+SESSION_LOG` |
| 3 | `personal-memory` | `task-3-healthcare-authority`: `guardrails`, healthcare information guidance | guardrails `READ`; information request `QUERY+SESSION_LOG` |

`task-1-campus-authority` is intentionally task-specific. A future shared
campus authority may be appropriate for a different experiment, but this
fixture's exact contents and permissions are part of Task 1's condition.

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

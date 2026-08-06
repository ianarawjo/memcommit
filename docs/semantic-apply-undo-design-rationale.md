# Semantic apply and command-unit Undo

## Invariant

An apply action is one command unit even when it writes both a Context and a
saved semantic artifact. Undo must restore the Context pre-image and remove the
artifact's effective `APPLIED` state; Redo must restore both. A target-only
restore is an inconsistent partial operation.

The Context checkpoint is the durable authority linking the two records. A
companion artifact may change state only after its session UID, change-set
digest, original checkpoint UID, and result or proposal identities match that
checkpoint. Restoration happens under the command and affected-Context locks,
with exception rollback for both records. Crash atomicity remains outside this
prototype until a transaction journal exists.

## Current coverage

| Apply flow | Applied-state source | Undo behavior |
| --- | --- | --- |
| Meld | Saved Meld session plus target checkpoint | Context and session restore together; `APPLIED` returns to `READY_TO_APPLY` |
| Atomize Grounding | Saved grounding dialogue plus Context checkpoint | Context and dialogue restore together; `APPLIED` returns to `READY_TO_APPLY` |
| Saved Atomize analysis, in-place or `--save-as` | Applied state is projected by matching the current Context to the exact analysis checkpoint | Undo restores the reviewed pre-apply frame and projects the analysis as `CURRENT`; Redo restores the exact applied frame and projects `APPLIED`. A save-as destination retains its separate `init` baseline checkpoint. |
| Saved Translation view, in-place or `--save-as` | The view is immutable planning evidence; materialization is represented by the `translate` checkpoint | Undo/Redo restores the exact untranslated/translated Context frame. A save-as destination retains its separate `init` baseline checkpoint. |
| Forget apply | No separately stored applied-state flag exists; the Context snapshot and `forget` checkpoint are authoritative | Undo/Redo restores the complete applied batch as one command unit. |
| Other direct Context mutations | Derived from current Context/checkpoint history | Context restoration already changes the projection; no companion flag exists. |
| Local or granted Update | Saved Update receipt, sometimes across Profile stores | Undo retains the exact receipt under `undone`; Redo restores `applied`. Granted-target restoration reverses the authority restore if participant receipt CAS fails |
| Sever | Saved Sever session plus creation of a new output Context | Undo removes the exact Result from the ordinary namespace, returns the session to `REVIEWING`, and retains its Context record and complete checkpoint log in a private command archive. Redo restores the same Context identity, application receipt, and log before appending a `redo` checkpoint. |

Read-only `mem diff` treats the saved Update receipt as one endpoint unit too.
An Update may bind a granted Source, a granted Target, or both, so freshness
inspection revalidates every present frozen Grant binding before comparing the
current frames. A granted Source must never be reopened from the active
Profile's local store merely because its Target is local. Revocation or
authority drift leaves the recorded diff inspectable but marks it revoked or
stale under the same fail-closed presentation used for a granted Target.

### Reversible Context creation

Sever is deliberately narrower than general Context-lifecycle Undo. Its apply
checkpoint must carry an exact versioned `context_creation` receipt and match
the saved Sever session's output UID, original checkpoint UID, and result
Memory UIDs. The command stack admits only that proven creation shape; ordinary
`init`, `branch`, import, rename, and delete operations remain outside Undo.

Undo cannot keep its receipt only inside the Result Context because successful
Undo makes that Context absent. It therefore moves the exact `context.json`
and checkpoint directory into a Profile-private command archive while holding
the command, graph, and Context locks. The archive remains part of command-stack
reconstruction, so the `sever` and `undo` records survive while the public
Context is absent. Redo rejects a reused output name or an edited review
session, restores the archived files, and appends its normal checkpoint-bound
restoration receipt. A failed session CAS moves the files back and removes the
provisional restoration checkpoint.

This archive is retained history, not a selectable Context and not a general
undelete facility. Like multi-file Context restoration, it provides
exception rollback but not a durable crash-recovery transaction journal.

### Non-Context Apply boundaries

External Share delivery is intentionally not made redoable by local command
history: replay would be a second externally visible transmission, not a local
state restoration. Named Ground revisions likewise remain under their exact
Ground-command approval and CAS protocol rather than being reinterpreted as
Context checkpoint commands. Query, Compare, Review-only reports, and saved
workbench navigation do not have a Context Apply boundary.

## Forward rule

A new apply flow must declare whether applied state is derived or separately
stored. Separately stored state must register a validated Undo/Redo companion
before the flow is considered complete. Cross-store and Context-lifecycle
flows must fail closed unless every owner can be exception-atomically restored;
they must not simulate success by changing only a UI label. A durable
cross-store crash-recovery journal remains a stronger future boundary than the
current reverse-on-failure granted Update protocol.

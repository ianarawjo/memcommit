# Semantic apply and command-unit Undo

Undo and Redo now enter separate operation adapters under
`memcommit.application.operations.undo` and `memcommit.application.operations.redo`. Their common
granted-versus-local stack selection lives in
`memcommit.application.capabilities.command_recovery.execution`; command modules retain only syntax, error
mapping, and receipt presentation. This shares the authority fallback
invariant without collapsing the two durable operation identities. See
`undo-redo-application-boundary-matrix.md`.

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

Successful Undo and Redo print one compact receipt line rather than replaying
restored Memory content. The line reconstructs a canonical effective `mem …`
command from frozen checkpoint metadata for each supported undoable operation;
it does not claim to reproduce the person's raw shell spelling. Context and
Memory selectors, source/target operands, scope switches, and apply switches
are retained where the checkpoint proves them. Raw Memory content and semantic
instruction text are represented by typed placeholders so Undo does not copy
private payloads into terminal scrollback. Older or internal checkpoint shapes
fall back to the recorded command name instead of inventing operands. The
remaining fields are the exact affected Context count, total affected Memory
count, and `+`/`~`/`-` effect counts. A separate location list would duplicate
the command operands and is omitted. Checkpoint receipt UIDs, detailed pre/post
content, descriptions, and the inverse-command hint remain available through
durable history and Trace rather than being expanded after every restoration.
This is presentation minimization only; the checkpoint and command-unit
records retain their complete recovery contract.

## Current coverage

| Apply flow | Applied-state source | Undo behavior |
| --- | --- | --- |
| Meld | Saved Meld session plus target checkpoint | Context and session restore together; `APPLIED` returns to `READY_TO_APPLY` |
| Atomize Grounding | Saved grounding dialogue plus Context checkpoint | Context and dialogue restore together; `APPLIED` returns to `READY_TO_APPLY` |
| Saved Atomize analysis, in-place or `--save-as` | Applied state is projected by matching the current Context to the exact analysis checkpoint | Undo restores the reviewed pre-apply frame and projects the analysis as `CURRENT`; Redo restores the exact applied frame and projects `APPLIED`. A save-as destination retains its separate `init` baseline checkpoint. |
| Saved Translation view, in-place or `--save-as` | The view is immutable planning evidence; materialization is represented by the `translate` checkpoint | Undo/Redo restores the exact untranslated/translated Context frame. A save-as destination retains its separate `init` baseline checkpoint. |
| Forget apply | No separately stored applied-state flag exists; the Context snapshot and `forget` checkpoint are authoritative. An accepted all-KEEP result changes no Context and writes no checkpoint. | Undo/Redo restores a nonempty applied batch as one command unit; an all-KEEP completion needs no recovery unit. |
| Other direct Context mutations | Derived from current Context/checkpoint history | Context restoration already changes the projection; no companion flag exists. |
| Local or granted Update | Saved Update receipt, sometimes across Profile stores | Undo retains the exact receipt under `undone`; Redo restores `applied`. Granted-target restoration reverses the authority restore if participant receipt CAS fails |
| Sever | Saved Sever session plus creation of a new output Context | Undo removes the exact Result from the ordinary namespace, returns the session to `REVIEWING`, and retains its Context record and complete checkpoint log in a private command archive. Redo restores the same Context identity, application receipt, and log before appending a `redo` checkpoint. |

A retained granted-Update receipt may outlive the authority-side restoration
stack that it once named. It must not mask a newer ordinary command in the
active Profile. Undo and Redo therefore fall back to the active Profile's
command stack only when the granted authority reports that its corresponding
stack is empty. Revocation, authority drift, and exact-unit ordering failures
still fail closed rather than substituting an unrelated local command.

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

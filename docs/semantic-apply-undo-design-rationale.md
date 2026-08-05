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
| Ordinary Atomize and direct Context mutations | Derived from current Context/checkpoint history | Context restoration already changes the projection; no companion flag exists |
| Local or granted Update | Saved Update receipt, sometimes across Profile stores | Undo retains the exact receipt under `undone`; Redo restores `applied`. Granted-target restoration reverses the authority restore if participant receipt CAS fails |
| Sever | Saved Sever session plus creation of a new output Context | Requires command-unit Context creation/deletion restoration before the session can safely return to `REVIEWING` |

## Forward rule

A new apply flow must declare whether applied state is derived or separately
stored. Separately stored state must register a validated Undo/Redo companion
before the flow is considered complete. Cross-store and Context-lifecycle
flows must fail closed unless every owner can be exception-atomically restored;
they must not simulate success by changing only a UI label. A durable
cross-store crash-recovery journal remains a stronger future boundary than the
current reverse-on-failure granted Update protocol.

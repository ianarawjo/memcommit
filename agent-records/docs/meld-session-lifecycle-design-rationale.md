# Meld saved-session lifecycle

Last reviewed: 2026-08-31.

## Current lifecycle

Meld stores one Target-scoped candidate review. `open` returns the session and
its opaque canonical-digest version. Restart and resolution must submit that
exact version, and stale requests stop before Update or Target mutation.

```text
Start/Restart
→ AWAITING_REPLY candidate review
→ resolve complete decision set
   → AWAITING_REPLY next post-image round, or
   → APPLIED verified receipt
```

A candidate session has no proposal turns, relation-analysis seed, choice
branches, preservation transition, or separately ready/applyable proposal. Its
durable review contains the complete candidate Context, frozen Source-claim
ledger, exact Audit, Resolve issues, active forced Audit keys, and round
revision. One `resolve_meld` call finalizes the round, invokes Update once,
re-Audits, verifies Source coverage, and applies only when no unforced issue
remains.

`APPLIED` is terminal evidence. Its candidate review is replaced with the exact
verified post-image and post-image Audit, and the application receipt binds the
proposal digest, checkpoint UID, and ordered Result Memory UIDs. Active forced
keys remain as explicit unresolved evidence and are counted in console and
external receipts.

An exact Restart reconstructs the candidate from frozen source inputs rather
than from the prior session. Candidate identity excludes session UID, so an
unchanged restart reuses the exact stored Audit. Restart replaces the session by
CAS only after the complete new review exists. A failed provider call leaves the
prior saved review active.

## Historical sessions

Schemas before the candidate contract retain their relation ledger, proposal
turns, assessments, and application receipts so Review and historical evidence
remain decodable. They are read-only through current console and external
routes. The former comment, preserve, defer, destination-change, and separate
Apply transitions are not compatibility execution paths; a person must Restart
to create a current candidate review.

The legacy model and runtime files remain temporarily because old session and
checkpoint readers still require their exact schemas. Their presence does not
make them production owners. New Start, Restart, Resolve, console, Python, and
agent routes call `runtime.preparation`, `meld.resolution`, and
`runtime.candidate_resolution` only.

## Persistence and concurrency

- Start requires a session-free Target. Symmetric create-target publishes the
  empty Target and initial candidate session together.
- Restart and each next-round publication use the exact prior session digest.
- Apply reloads and verifies both Source frames and the Target immediately
  before writing.
- A blocking post-image Audit or missing Source claim publishes no Target
  change. A blocking Audit may CAS-save the complete next review.
- Candidate Target publication and final session-receipt publication share one
  lock scope and roll the Context record, checkpoint, and session back together
  on a process exception. They remain consecutive physical writes rather than
  one crash-atomic journaled transaction. A candidate-specific recovery proof
  is still required for a crash between those writes; legacy proposal recovery
  is not reused because its evidence contract differs.

## Public contract

| Action | Version | Provider work | Effect |
| --- | --- | --- | --- |
| Start | Target must have no session | initial Audit and directions if issues | saves initial candidate review |
| Open | none | none | read-only projection |
| Restart | exact current version | reused/new Audit and directions | CAS-replaces review |
| Resolve | exact current version | one Update, post-Audit, coverage, and directions only if another round opens | saves next round or applies verified Target |

This single lifecycle is used by console, `MemCommitClient`, and the agent
adapter. There is no public method for comment, preserve, defer, or separate
Apply.

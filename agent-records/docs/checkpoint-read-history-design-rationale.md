# Checkpoint-read History design rationale

## Problem

Memcommit already had one canonical retained-History topology, but checkpoint
consumers still crossed that boundary unevenly. Context and Memory Trace used
the verified `HistoryGraph`, and Rationale consumed the same History evidence,
while plain Log and checkpoint Diff independently read raw checkpoint records.
There was also no authority value between two unsafe extremes: ordinary
`READ`, which exposes only a Context's current content, and full access to the
authority owner's retained checkpoint log.

The required history right is not another CRUD verb. It describes which
retained states may be read. It must also remain separate from the command
attempt ledger and Study action ledger: those ledgers are process or research
audit evidence, not Context state ancestry.

## Canonical History boundary

`memcommit.application.capabilities.history` remains the sole canonical owner
of retained Context and Memory History. `HistoryGraph` continues to own typed
operation, step, occurrence, effect, and relation topology. A checkpoint UID is
evidence for an operation step and is not promoted to operation identity.

`CheckpointHistorySlice` is a narrow query over the same normalized checkpoint
timeline. It freezes the raw checkpoint list once, retains both archived and
currently selectable records, and provides exact `reference`, anchored
`after`, mechanical `transitions`, and complete before/after `revision`
queries. It does not introduce a second lineage graph. Diff and Log now consume
this slice: Diff asks it for the exact revision, while plain and semantic Log
share its selectable records and timeline. Their existing output contracts do
not change.

Context Trace, Memory Trace, MemoryRef Trace, and Rationale retain their
existing `HistoryGraph`-based projections. Focused tests verify those outputs
while the lower checkpoint consumers converge; no command or Study ledger is
accepted by the History evidence port.

## CheckpointRead contract

`CheckpointRead` is a typed authority capability bound to one durable Context
UID and one of two scopes:

- `Reference(checkpoint_uids)` is a nonempty, immutable exact set. A caller may
  request any subset, but cannot infer a growing range from it.
- `Embed(anchor_checkpoint_uid)` includes the anchor and every later retained
  checkpoint in the same Context's canonical sequence. It may authorize an
  exact Reference inside that range or a later Embed anchor.

Timestamp comparison is not an authorization rule. Coverage is decided from
the canonical retained sequence, and every request must match the History
slice's Context UID. A branch has a different Context UID, so an Embed never
crosses into it merely because lineage relates the two Contexts.

An authority Grant stores zero or more typed checkpoint reads. Current Context
`READ` remains a prerequisite, but it does not imply any checkpoint right.
Grant creation and revision reject rights outside the Grant's frozen Context
bindings, rights whose exact checkpoint or anchor is not retained, and
retained-history rights when `READ` is absent. Registry schema version 4
persists the new field; versions 1–3 load with an empty scope, so existing
Grants do not silently acquire history access.

The authorization service fails a Grant with no candidate right before opening
the authority checkpoint log. After ordering-dependent coverage is checked, it
returns an `AuthorizedCheckpointHistory` projection that exposes only the
requested checkpoints; record, revision, and transition lookup fail outside
that window. Local ownership may construct the same bounded value without an
external Grant.

## Adapter and audit boundary

This contract does not invent command-line syntax for authoring
`CheckpointRead` scopes. Existing granted Trace remains blocked because its
current report expects a complete History graph; neither a Reference nor a
later Embed necessarily authorizes that complete graph. Diff requests one exact
checkpoint Reference and renders only that revision against its retained
pre-image after authorization. Other granted History adapters must likewise
request and render a bounded window before exposing retained evidence.

The command-attempt ledger and Study action ledger remain independent durable
audit streams. They may annotate that a command ran or record a study
interaction, but they are not checkpoint records, cannot satisfy a
`CheckpointRead`, and do not enter `HistoryGraph` reconstruction.

## Alternatives and limitations

Adding `HISTORY` to the CRUD permission set was rejected because it would
collapse current content and retained states into one unbounded capability.
Treating Reference and Embed as ordinary Memory relationships was rejected
because these values authorize checkpoint evidence, not Context placement or
lineage edges. Using timestamps for Embed coverage was rejected because
timestamps are payload evidence rather than the canonical retained order.

The History evidence source still reads the current Context and checkpoint log
through two existing Store calls; this change makes all projections reuse those
results but does not add a new cross-file read transaction. Existing validation
and unrecorded-current warnings therefore remain the consistency boundary. A
future atomic evidence snapshot can strengthen that boundary without changing
`CheckpointHistorySlice` or `CheckpointRead` semantics.

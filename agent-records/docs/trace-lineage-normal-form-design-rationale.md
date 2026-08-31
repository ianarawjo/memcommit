# Trace lineage normal-form design rationale

## Problem

Context Trace and Memory Trace previously reconstructed the same retained
history with different organizing subjects. Context Trace grouped direct
Memory deltas by checkpoint. Memory Trace independently derived richer events,
built a UID adjacency table, selected one connected component, and counted
operations with a second adjacency table. MemoryRef Trace used a third
occurrence-history path and then attached a target Memory Trace. The reports
were useful, but there was no internal value that could state that all three
were projections of the same operation and occurrence lineage.

That split also obscured three invariants. A checkpoint is evidence for an
operation, not necessarily the operation's durable identity; one operation UID
may be evidenced by several checkpoints. A repeated Memory UID is not one
timeless node; it has distinct occurrences before and after operations. Embed,
Reference, and Grant are different relations: Embed/Reference connect
occurrences, while Grant authorizes a read route and is not ancestry.

## Decision

Canonical History now normalizes verified evidence under
`memcommit.application.capabilities.history` before Trace, Log, or Rationale
projects it. The package names describe the actual responsibilities:

- `model/topology.py` owns immutable operation nodes, operation evidence steps,
  Context/Memory/MemoryRef occurrence nodes, typed effects, typed relations,
  and deterministic graph queries.
- `reconstruction/history_graph_reconstruction.py` consumes verified Context
  states, Memory events/frames, and typed MemoryRef occurrence evidence and
  assembles that topology. It retains the exact verified payloads needed by
  downstream projections.

`HistoryOperation` uses a verified command-operation or operation UID when
one exists. Otherwise it falls back to the exact Context/checkpoint coordinate;
an unrecorded current change receives a synthetic identity derived from its
typed position. `HistoryStep` represents each exact checkpoint or
unrecorded-current evidence occurrence. Consequently several steps may point
to one operation node without making a checkpoint UID pretend to be the
operation UID.

`HistoryOccurrence` includes a durable Context/subject coordinate and a state
anchor. The same Memory UID before and after an Edit is therefore two
occurrences connected by `CONTINUES_AS`, while a Split, Absorption,
Translation, Branch, or recorded Merge adds `DERIVED_FROM`. Direct ownership
uses `CONTAINS`. Live placement uses `EMBEDS`; immutable snapshot placement
uses `REFERENCES`. `INPUT` and `OUTPUT` attach exact occurrence endpoints to
the operation that consumed or produced them.

## Projection contracts

Context projection follows the frozen root Context's ordered operation steps.
It therefore retains checkpoints with no direct Memory delta and produces the
same checkpoint-shaped JSON as before. Its current frame is the set of typed
`CONTAINS` edges from the frozen current Context occurrence.

Memory projection resolves a selector from graph occurrences, follows only the
typed lineage-producing Memory effects, and selects the corresponding verified
event payloads. The interactive change count also uses operation nodes from
the graph, while preserving the former count boundary that does not broaden a
candidate through cross-Context Merge. Origins, current states, semantic
analysis attachments, and cross-Context Merge receipt discovery keep their
existing report contracts.

MemoryRef projection selects the occurrence evidence assembled into the same
graph. Its live or snapshot target is an `EMBEDS` or `REFERENCES` edge, then the
existing independent target-authority check decides whether a target Memory
Trace can be attached. The occurrence and target identities are not collapsed.

## Determinism and evidence boundary

Graph identity and connectivity use typed fields only: Context UID, Memory or
relationship UID, state anchor, verified operation UID, checkpoint UID,
effect kind, and relation kind. Timestamp, command label, description, reason,
and Memory content remain payload or digest evidence. Changing descriptive
text cannot change operation identity, component membership, or graph edges.
Tests rebuild the same evidence with unrelated descriptions and require the
same operation and relation topology.

History verification flattens checkpoints, normalizes snapshots, and validates
operation receipts. History reconstruction maps that verified evidence to
typed effects and attaches them to operations and occurrences; Trace then
selects a Context, Memory component, or MemoryRef occurrence. These are
separate stages, but there is no second UID-component or operation-count
construction algorithm beside the topology.

## Authority and relationship boundaries

Grant is deliberately absent from the ancestry relation vocabulary. A Grant
may annotate or authorize an `EMBEDS` route, but its attachment Context is not
a parent and its public name is not a lineage edge. READ-granted current
content therefore keeps the existing current-view Trace result; it does not
silently authorize the owner's checkpoint log. The later explicit
[`CheckpointRead`](checkpoint-read-history-design-rationale.md) contract can
authorize an exact Reference or same-Context anchored Embed window, but it is
still an access boundary over this graph rather than an ancestry relation.
Existing granted Trace remains blocked until its adapter can request and
render such a bounded graph projection.

Relationship targets are non-selectable in an owner's direct-Memory catalog.
An Embed edge can make a target inspectable through its own authorized route,
but it does not add the target Memory UID to the owner's UID component.
Lexical Context ancestry also remains independent from Embed reach.

## Compatibility and limitations

The public `ContextHistorySlice`, `MemoryHistory`, and
`MemoryReferenceTraceReport` dictionaries, event order, selector ambiguity,
component membership, current/original selection, and picker counts are
unchanged. Golden tests compare the old Context timeline projection with the
new topology projection and retain focused Memory/Reference JSON and selection
contracts. The old pure `context_trace_from_timeline` function remains as a
compatibility/golden projector, but production Context Trace uses the shared
topology.

Cross-Context Merge receipts must still be catalogued before all participating
owner Contexts can be loaded. That discovery index is an authority-safe way to
find which local graphs to assemble; verified Merge events then enter the same
typed event vocabulary. The topology does not open unrelated Context content,
query-only sources, or hidden authority checkpoints.

Using checkpoint nodes as the only operation identity was rejected because it
splits multi-checkpoint command units. Using one node per UID was rejected
because it erases temporal occurrences. Parsing command descriptions was
rejected because prose is neither stable nor authoritative. Treating Grant
attachments as graph parents was rejected because authorization metadata does
not define public hierarchy or provenance ancestry.

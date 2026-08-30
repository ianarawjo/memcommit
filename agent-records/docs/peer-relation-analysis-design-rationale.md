# Peer Relation Analysis design rationale

## Problem

The exhaustive two-Context relation ledger was physically nested under the
Compare operation even though Meld also consumes it as the semantic basis for
dispositions and proposals. That made a read-only presentation operation look
like the owner of a reusable judgment capability and forced Meld to depend on
Compare implementation modules.

Update appeared related for a different reason: its provider prompt asks the
model to avoid duplicates and account for conflicts. Inspection showed that
Update does not import Compare at all. It currently owns a directional change
planner and persists only exact ADD, EDIT, and REMOVE operations; it has no
typed issue artifact or audit/resolve iteration.

## Decision

`application.capabilities.memory_issue_analysis.peer_relations` owns the
complete source-linked relation model, evidence projection, provider contract,
bounded execution, and local or Grant-bound repositories. Compare owns its
summary, Run/Open/Refresh session application, and presentation. Meld consumes
the capability through `MemoryRelation*` names and owns only the conversion
from relations into Meld dispositions, issues, proposals, dialogue, and Apply.

The existing `Comparison*` classes, provider operation labels, storage
directories, prewarm vocabulary, and Meld `comparison_seed` field remain as
wire-compatibility names. They are aliases or serialized records, not physical
ownership by the Compare operation. Migrating those durable names would add a
schema and store migration without changing responsibility.

Update is not mechanically wired to this peer analysis. Its correct shared
analysis boundary is after a complete proposed Target post-image exists. That
future pass must analyze ambiguity, redundancy, and conflict in the whole
Target frame, retain only findings intersecting changed Memory UIDs, and feed
those findings into an explicit Audit/Resolve revision loop before Apply.
Running hidden checks without persisting their questions and responses, or
blocking Apply with findings the person cannot inspect and resolve, would
create an incomplete lifecycle. The current change therefore records this
boundary but does not invent that lifecycle.

## Invariants and limitations

- Compare and Meld use the same exhaustive peer-relation ruleset and decoder;
  neither imports the other's operation package.
- Compare remains read-only; relation reuse does not grant Meld Apply authority.
- Meld still revalidates Source, Grant, retention, CAS, and target ownership at
  its own runtime boundary.
- Update has no Compare dependency today. Its existing exact-plan validation
  remains unchanged until post-image issues can be stored, shown, revised, and
  rechecked as one operation-owned iteration.
- The active-store `comparison-analyses` names and legacy prewarm APIs remain
  compatibility boundaries. Renaming them is intentionally not part of this
  ownership correction.

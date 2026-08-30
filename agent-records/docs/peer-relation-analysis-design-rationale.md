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
summary, Run/Open/Refresh session application, labelled presentation wrapper,
and receipt. Meld consumes the capability through `MemoryRelation*` names and owns only the conversion
from relations into Meld dispositions, issues, proposals, dialogue, and Apply.
Every new Meld Start and Restart now obtains this basis before constructing its
reviewed session. Directional cache misses no longer fall back to a second
Meld-owned relation classifier; they run the same capability analysis and then
enter the authority-specific materialization policy.

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
- New symmetric, directional, focused, and inline Meld sessions all retain an
  exact relation basis. Seedless Directional sessions are read/resume
  compatibility data, not a production Start shape.
- Initial Directional provider output cannot contain relation or source-
  assignment fields. The host reattaches the typed basis before validating
  issues and proposals.
- Compare remains read-only; relation reuse does not grant Meld Apply authority.
- Meld still revalidates Source, Grant, retention, CAS, and target ownership at
  its own runtime boundary.
- Update has no Compare dependency today. Its existing exact-plan validation
  remains unchanged until post-image issues can be stored, shown, revised, and
  rechecked as one operation-owned iteration.
- The active-store `comparison-analyses` names and legacy prewarm APIs remain
  compatibility boundaries. Renaming them is intentionally not part of this
  ownership correction.

## Python ownership completion (2026-08-30)

The capability-neutral names are now the authored Python definitions rather
than aliases over Compare-named classes. `MemoryRelationAnalysis`, its input,
frames, relations, issues, evidence projection, provider decoder, execution
result, and repositories are the concrete definitions under
`memory_issue_analysis.peer_relations`. Existing `Comparison*` imports are
identity-preserving aliases to those objects, so callers do not receive a
second type hierarchy and persisted JSON remains readable without migration.

The detailed terminal projection moved to the operation-neutral
`terminal.components.peer_relations.presentation` component. Compare wraps it
with Compare commands and receipts; Meld calls the component directly. Meld
also reaches Study-installed relation artifacts through a neutral prewarm
facade. That facade deliberately delegates to the legacy Compare-labelled
registry records because their operation labels, artifact kinds, cache keys,
and receipt paths are durable compatibility data.

This ownership correction changes neither the peer-relation algorithm nor its
provider operations (`compare_contexts` and its repair operation), serialized
Meld `comparison_seed` field, active-store directories, prewarm evidence, nor
the visible Compare-labelled report heading retained by the current Meld UI.
It also does not construct a virtual combined candidate, run Audit, enter an
Audit–Resolve loop, or invoke Update. Those steps depend on a separately stable
Update revision contract and remain outside this change.

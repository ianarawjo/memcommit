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

## Single current contract (2026-09-06)

The user requested one current comparison contract and explicitly declined
both older-result compatibility and rule-change-driven regeneration. The
prototype has no released comparison format to preserve. Retaining hand-edited
semantic revision labels, supported-version lists, and alternate decoders
would add maintenance without a current requirement.

`MemoryRelationInput` and `MemoryRelationAnalysis` no longer carry
`ruleset_version`. The provider has no contract-version constants or supported
version list. It accepts exactly the advertised response shape: `overview`,
`reports`, `paired_relations`, `distinct_relations`, `source_assignments`, and
`issues`. The former flat `relations` response and omitted-assignment paths
are rejected; the existing one bounded repair turn may still obtain a valid
current response.

Saved analyses use one strict structural shape. `schema_version: 4` continues
to identify that shape, but schema 1–3 readers, optional semantic reports,
missing descendant-scope defaults, and the old `ruleset_version` field are
removed. Reports and scope are required. Focused frames must carry their exact
selected Memory UID, and missing evidence provenance cannot suppress source
identity comparisons. These changes supersede the artifact-readability claims
in the earlier ownership history above. Existing files are neither migrated,
deleted, silently ignored, nor overwritten when decoding fails.

Saved reuse and exact Open retain ordered frame identity, selection, scope,
Context/Memory digests, provenance, and Grant revalidation. They do not compare
semantic revisions. A prompt edit alone can therefore leave a saved result
reusable; this is the selected behavior, not an implicit freshness guarantee.
Explicit Refresh remains available, but no manual-refresh requirement, hidden
regeneration, or replacement hash has been introduced.

UID-plus-canonical-digest CAS still protects publication and exact reviewed
Refresh. These tokens describe the saved artifact, not the ruleset, and remain
necessary to detect competing writes. Meld consumes the same current relation
model while retaining its own authority and Apply checks. Compare-labelled
Python aliases, provider operation names, and store paths retain their existing
ownership contracts; unrelated operations' versioning is outside this change.

Verification in the primary checkout: 261 related tests passed across Compare,
summary rules, evidence/focus identity, Grant consumers, Meld, semantic
execution, retained-artifact search, and operation-evidence integrity. Three
unrelated failures were reproduced against a temporary source copy with this
task's implementation changes removed, then excluded from that focused run:

- `test_relative_peer_locator_errors_before_provider`: the endpoint error text
  no longer includes the resolved Context name expected by the test;
- `test_new_compare_and_update_setup_include_a_granted_target`: the endpoint
  catalog returns more values than the test's four-value unpacking expects;
- `test_update_between_distinct_grants_writes_only_accepting_target`: its
  Profile fixture fails the existing one-placement-per-Grant validation.

Regression coverage now verifies version-free saved round trips and reuse,
rejection of retired saved/provider shapes, exact focused selection, retained
provenance checks, source-change suppression, and competing-publication CAS.
`python scripts/verify_operation_evidence.py --check` and undefined-name lint
also pass. The historical terminal capture harness was adapted to the changed
internal payload; no visible current terminal flow or capture image changed.

The focused commit was also tested independently of pending adapter/Meld
removals in the working tree. Comparison consumers still present in the
committed tree now omit the ruleset field and require reports; their Meld
seed adapters consume the current scope shape directly. The isolated tree
passed 127 Compare/public-adapter tests, 32 Grant tests, and two direct Meld
seed projection/round-trip tests. Existing endpoint, Grant, and legacy Meld
workflow failures were checked against the unmodified commit separately.
Pending removals and unrelated refactors were not folded into this change.

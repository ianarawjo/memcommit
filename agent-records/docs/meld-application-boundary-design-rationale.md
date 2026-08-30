# Meld application-boundary rationale

## Motivation

Meld originally let the CLI command own provider connection, assessment repair,
session mutation, optimistic persistence, destination relocation, preservation,
and Apply transactions. That made the TUI and scripted flags the only complete
entry point even though the same operation must also support Python and agent
adapters.

## Boundary

Meld now names its terminal-independent contracts by pipeline responsibility:

- `memcommit.application.operations.meld.preparation` owns the common typed
  Source/target boundary for a new or replacement pipeline. The opaque expected
  version is an initial-condition difference, not a second application.
- `memcommit.application.operations.meld.planning` owns one frozen cached or
  provider-backed semantic planning turn, repair, and all-or-nothing
  publication.
- `memcommit.application.operations.meld.proposal_iteration` owns saved
  snapshots, exact issue/option responses, pending turns, defer,
  provider-free preservation, and destination changes.
- `memcommit.application.operations.meld.proposal_projection` projects the
  durable proposal session into the common read-only workbench.
- `memcommit.application.operations.meld.apply` owns reviewed Apply routing.
  `memcommit.application.operations.meld.runtime` supplies Source access,
  preparation, proposal-iteration persistence, cache, checkpoint, recovery,
  and mutation adapters.

The command remains responsible for argument and TUI presentation, progress
text, exact approval, and rendering. Direct CLI setup constructs
`MeldStartRequest` and enters the same runtime used by Python and agent
adapters. Compare ends at its own analysis/report boundary; a person starts
Meld separately, and Meld alone selects or creates its Result. The runtime returns one frozen
`PreparedMeldExecution`; the CLI uses only its provider requirement and
read-only provisional view to choose a progress surface, then executes that
same value. It neither constructs a competing session nor repeats cache
lookup.

The former command-local Apply transaction, recovery, checkpoint-record, and
session-publication implementations were removed after their runtime adapters
were verified. Provenance tests now exercise the runtime-owned checkpoint
projection directly. A source-level boundary test prevents target or session
publication primitives from returning to `commands.meld`.

The normal terminal shortcut that conservatively completes an initial
symmetric assessment follows the same rule: the command may select that
provider-free behavior, but `run_meld_initial_preservation` clones and validates
the candidate while its MemoryStore repository publishes the exact session by
CAS. The adapter never calls a Store session-publication primitive directly.

## Cache invariants

A reusable Meld resolution branch is profile-local, hidden, immutable, and
keyed by the complete provider prompt, output schema, request-contract version,
and configured provider identity. Cache lookup happens before provider
construction. Only complete `ALL` or `REMAINING` follow-up reconciliations are
cached; an initial analysis and an isolated issue choice are not independently
composable final outcomes.

Saved completions are replayed through the ordinary decoder and session
validation. A cache miss is published only after the full response, repair if
needed, source/target revalidation, Grant checks, and exact session CAS. The
branch file uses first-writer-wins publication and rejects symlink storage.

## Pipeline-named physical ownership (2026-08-30)

The earlier terminal-independent extraction was organized by command actions:
Start, Restart, Assessment, Session, and Resolution. Later package moves split
large model and runtime files without changing those seams, so one direct
relation-first lifecycle remained physically described as several peer
applications. The present relocation preserves behavior while naming the
existing owners as Preparation, Planning, Proposal Iteration, and Apply.

The model follows the same evidence progression: `source_snapshot.py`,
`integration_proposal.py`, `proposal_session.py`, and `apply_effects.py`.
Runtime effects are named `source_access.py`, `preparation.py`,
`session_repository.py`, `proposal_iteration.py`, and `apply_transaction.py`. No empty
`candidate_context.py` or `integration_plan.py` is added before those durable
values exist. Creating the virtual combined candidate, composing shared Memory
Issue Analysis, and routing candidate revisions through Update remain the next
semantic implementation rather than being implied by this file move.

## Compatibility and limitations

The CLI and TUI keep their existing actions, order, progress surface, rendered
reports, session schema, checkpoints, and Grant behavior. Study-installed
branches use a separate operation adapter because their task-description and
baseline identity authorization is broader than ordinary profile-local
persistence. A matching immutable shared-bundle branch is replayed through the
same decoder, then promoted into the participant's hidden profile cache only
after the live Context and session checks pass. New-session construction now
has a terminal-independent runtime. `MemCommitClient` projects immutable Meld
review values and exposes start, open, comment, preserve, defer, and exact
Apply without importing terminal code. Every saved-session mutation requires
the opaque version returned by `open`; only Start and read-only Open omit it.
The shipped `memcommit_meld` agent adapter now maps a strict versioned JSON
action union to that facade and returns bounded errors without exposing
provider responses or host paths. CLI routing remains
visually compatible while no longer owning new-session persistence. Restart is
an explicit replacement of an existing target-bound session and remains a
separate CAS operation exposed by the CLI, Python facade, and agent adapter; it
is not implemented as a new start that first deletes or hides the durable prior
review. The public immutable session projection includes its opaque version so
nonterminal callers can make the same reviewed replacement decision.

## Post-TUI audit correction

The first extraction correctly removed durable session and Apply primitives
from the command, but its completion claim was too broad. `commands.meld`
continued to acquire or install an ordered Compare basis, construct a
provisional directional session, and repeat initial prewarm lookup before
calling `execute_meld_start` or `execute_meld_restart`. Python and agent starts
did not execute that identical preparation path, and new direct-Memory scope
controls had no typed application field.

The completion pass therefore preserves the existing application services and
adds one frozen Prepare/Execute boundary for Start and Restart. Provider
progress remains interface-owned, but whether provider work is required must
come from the prepared value rather than a second interface-side cache query.

The first completion step moved peer-relation execution out of `commands`.
Meld's runtime now owns exact/equivalent/projected/live acquisition for both
authority modes through
`application.capabilities.memory_issue_analysis.peer_relations`. This direction
was chosen so Python, agent, and terminal calls cannot disagree about which
relation cache shapes are safe.

## Unified relation-first Start (2026-08-30)

The former Directional miss path let the Meld provider classify relations and
materialize BASELINE changes in one completion, while Symmetric Meld always
started from a separately frozen peer-relation analysis. That was one semantic
responsibility split horizontally across two Start implementations: the same
source pair could receive one relation judgment from the shared capability or
a different judgment from Meld solely because a cache entry was absent.

New Start and Restart execution therefore use one ordered lifecycle:

1. freeze sources, scope, authority, target, and the saved-session CAS token;
2. reuse, project, or create one `MemoryRelationAnalysis`;
3. bind that exact analysis into the target-scoped `MeldSession`;
4. materialize through the authority-mode policy; and
5. publish the reviewed session, then use the existing resolution and Apply
   lifecycle.

For Context inputs the relation analysis is saved through the capability's
ordinary artifact/Grant boundary. An inline Memory has no independent Context
locator, so its analysis is retained only in the target-bound session. Exact
Memory focus is carried through both the analysis and Meld frames; neighboring
Memories remain context-only evidence.

The initial Directional materialization schema contains no relation or source-
assignment fields. The host reattaches the exact typed relations and imported
issues, so the provider can add only Directional-specific issues and exact
`EDIT`/`ADD` proposals. A resolved relation may become a single exact BASELINE
edit under Directional authority; that is a late materialization policy and
does not authorize relabeling, regrouping, or resolving a `CONFLICT` or
`UNCLEAR` relation. Such required issues remain in the existing review/resolve
loop. Symmetric materialization retains its conservative empty-Result policy.

Saved direct Directional sessions without a relation seed remain readable and
resumable as compatibility data, but production Start no longer creates that
shape. The later responsibility/file consolidation is now complete, and the
detailed relation presenter is operation-neutral; Compare retains only its
command-labelled wrapper and receipt. This change deliberately does not perform
Update post-image audit work.

Start and Restart preparation freezes authority, source frames, target state,
the saved-session CAS token, ordered relation reuse, and directional assessment
prewarm before any provider construction. A cache hit is executed from that
same value. A symmetric live miss performs one provider analysis, then enters
the ordinary exact relation-analysis installation boundary; that final installation may
observe a concurrently published exact result, but it does not repeat
equivalent or projection search. This preserves CAS safety without restoring
adapter-owned cache prediction.

Follow-up turns use the same pattern. `PreparedMeldTurnExecution` binds the
locally composed `PendingMeldTurn` to its exact hidden resolution-cache result,
provider request, and publication port. The CLI reads `provider_required` only
to decide whether to show progress and then executes that same value; the
Python facade and agent first call the same operation-owned Meld Resolution
preparer, then enter the same prepared execution. Provider connection timeout
policy also moved into `meld_runtime`, so an interface can observe progress
but cannot silently choose a weaker semantic-call bound.

The follow-up boundary previously converted a TUI option UID to an ordinal in
the interface, then converted that ordinal back to provider text in the CLI.
The CLI's scripted `--choice` path did the same independently, while Python and
agent callers could submit only free-form text. The corrected boundary carries
the exact option UID into
`memcommit.application.operations.meld.proposal_iteration`; only that operation layer
reads its frozen option text. Python exposes option UID and requires the
expected version for every comment, while the agent requires
`expected_version` for comment, preserve, defer, and Apply. Apply alone accepts
the exact reconstructed predecessor of an already applied receipt so a
repeated identical request recovers instead of creating a second checkpoint.
This prevents a reordered presentation or stale reviewed assessment from
silently changing a machine-submitted answer.

The final CLI Apply wrapper now calls `execute_meld_apply` directly. The
discarded outer application flow contributed only an identity review step and
duplicated the receipt checks already enforced by `run_meld_apply`; it owned no
authorization, CAS, recovery, rollback, or checkpoint behavior. Keeping that
wrapper would therefore create a second apparent lifecycle without adding a
safety boundary. The standalone generic flow and legacy Meld adapter remain
available for compatibility, but they are no longer part of production Meld
command execution.

## Detailed relation ownership (2026-08-30)

Meld no longer imports the Compare operation, Compare console presentation, or
the legacy Compare prewarm module. It consumes the concrete `MemoryRelation*`
model, execution, repository, and provider contracts and calls the shared
peer-relation presenter directly. Study compatibility is isolated behind
`study_scenarios.legacy.prewarm.peer_relations`, whose only purpose is to map
neutral callers onto existing Compare-labelled persisted artifacts.

The Meld session's Python field is `relation_analysis_seed`; the historical
`comparison_seed` attribute remains a compatibility property and the JSON key
is unchanged. Likewise, old construction methods and schema constants are thin
aliases. They do not own logic. The provider payload field `comparison_basis`
and directional contract version remain unchanged because renaming them would
invalidate saved provider/prewarm evidence without improving the runtime
boundary.

No Audit–Resolve or Update revision cycle is introduced here. Meld still stops
at its existing proposal iteration and Apply behavior; a future combined-
candidate pipeline must wait for Update to expose a stable revision contract.

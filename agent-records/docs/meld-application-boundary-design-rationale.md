# Meld application-boundary rationale

## Motivation

Meld originally let the CLI command own provider connection, assessment repair,
session mutation, optimistic persistence, destination relocation, preservation,
and Apply transactions. That made the TUI and scripted flags the only complete
entry point even though the same operation must also support Python and agent
adapters.

## Boundary

Meld now separates its terminal-independent contracts:

- `memcommit.application.operations.meld.assessment_application` owns one frozen semantic
  turn, cache replay,
  provider execution, one repair attempt, and all-or-nothing publication.
- `memcommit.application.operations.meld.session_application` owns saved-session snapshots,
  pending dialogue
  turns, defer, provider-free preservation, and destination-change requests.
- `memcommit.application.operations.meld.resolution_application` projects a saved
  assessment into the common
  Resolution contract, validates exact issue/option UIDs against its opaque
  version, and translates a valid choice to operation-owned provider guidance.
- `memcommit.application.operations.meld.application` owns reviewed Apply routing.
  `memcommit.application.operations.meld.runtime` supplies the
  MemoryStore, Grant, checkpoint, recovery, cache, and provider adapters.
- `memcommit.application.operations.meld.start_application` owns the canonical
  source/target request and
  validates the resulting initial review. The runtime repeats source authority,
  transfer, Compare-basis, empty-target, and session-absence checks before it
  publishes either a directional review or a symmetric Result session.
- `memcommit.application.operations.meld.restart_application` owns replacement of an
  existing target-bound
  review under an opaque expected version. Start and restart share the same
  authorization, Compare, cache, and construction runtime, but restart must
  observe the old session before provider construction and replace it by CAS.

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

The first completion step moved Compare execution out of `commands`. Meld's
runtime now owns symmetric exact/equivalent/live acquisition and directional
exact/equivalent/projected acquisition. The neutral
`memcommit.comparison_execution` module contains authorization, CAS, Grant
revalidation, installation, and lazy provider construction; the legacy
`commands.comparison_execution` module retains only terminal wait rendering
and re-exports for compatibility. This direction was chosen so Python, agent,
and terminal calls cannot disagree about which Compare cache shapes are safe.
It intentionally does not make a directional Compare mandatory: an actual
miss still enters the established directional Meld assessment path.

Start and Restart preparation freezes authority, source frames, target state,
the saved-session CAS token, ordered Compare reuse, and directional assessment
prewarm before any provider construction. A cache hit is executed from that
same value. A symmetric live miss performs one provider analysis, then enters
the ordinary exact Compare installation boundary; that final installation may
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
`memcommit.application.operations.meld.resolution_application`; only that operation layer
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

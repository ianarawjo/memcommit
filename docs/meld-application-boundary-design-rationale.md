# Meld application-boundary rationale

## Motivation

Meld originally let the CLI command own provider connection, assessment repair,
session mutation, optimistic persistence, destination relocation, preservation,
and Apply transactions. That made the TUI and scripted flags the only complete
entry point even though the same operation must also support Python and agent
adapters.

## Boundary

Meld now separates three terminal-independent contracts:

- `meld_assessment_application` owns one frozen semantic turn, cache replay,
  provider execution, one repair attempt, and all-or-nothing publication.
- `meld_session_application` owns saved-session snapshots, pending dialogue
  turns, defer, provider-free preservation, and destination-change requests.
- `meld_application` owns reviewed Apply routing. `meld_runtime` supplies the
  MemoryStore, Grant, checkpoint, recovery, cache, and provider adapters.
- `meld_start_application` owns the canonical source/target request and
  validates the resulting initial review. The runtime repeats source authority,
  transfer, Compare-basis, empty-target, and session-absence checks before it
  publishes either a directional review or a symmetric Result session.
- `meld_restart_application` owns replacement of an existing target-bound
  review under an opaque expected version. Start and restart share the same
  authorization, Compare, cache, and construction runtime, but restart must
  observe the old session before provider construction and replace it by CAS.

The command remains responsible for argument and TUI presentation, progress
text, exact approval, and rendering. Both direct CLI setup and the
Compare-to-Meld handoff now construct `MeldStartRequest` and enter the same
runtime used by Python and agent adapters. The CLI may construct a provisional
directional frame solely to decide whether a provider progress surface is
needed, but that frame is never persisted; the runtime repeats the cache and
authority decision before publication. It must not become the semantic or
persistence authority.

The former command-local Apply transaction, recovery, checkpoint-record, and
session-publication implementations were removed after their runtime adapters
were verified. Provenance tests now exercise the runtime-owned checkpoint
projection directly. A source-level boundary test prevents target or session
publication primitives from returning to `commands.meld`.

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
Apply without importing terminal code. The shipped `memcommit_meld` agent adapter
now maps a strict versioned JSON action union to that facade and returns bounded
errors without exposing provider responses or host paths. CLI routing remains
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

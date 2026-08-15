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

The command remains responsible for argument and TUI presentation, progress
text, exact approval, and rendering. It must not become the semantic or
persistence authority.

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
reports, session schema, checkpoints, and Grant behavior. This step adds only
profile-local branch reuse. Study-installed hidden branch lookup is a separate
adapter because its task/fixture authorization is broader than ordinary
profile-local persistence. Initial Meld construction and public Python/agent
facades also remain later rollout steps; no public API is declared here.

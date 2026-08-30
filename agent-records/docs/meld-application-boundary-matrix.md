# Meld application boundary matrix

Last reviewed: 2026-08-29.

## Status

`VERIFIED` for the currently implemented CLI, TUI, public Python, agent, and
MCP routes. The operation owns one typed Start/Restart, saved-turn,
cache/provider, session-CAS, and Apply lifecycle. A future public destination
relocation adapter is not part of the current route set and does not create a
second implementation today.

## Goal

Meld must produce the same authorized, cache-aware, versioned result whether
it is invoked through the CLI, Python facade, or agent tool. Terminal adapters
may collect values and present progress or review state, but they are not an
independent source of provider, cache, session, or Apply behavior.

## Package ownership

The canonical terminal-independent owners now live together under
`memcommit.application.operations.meld`. `preparation.py` owns the shared
Start/Restart request boundary; `planning.py` owns one frozen cached or
provider-backed semantic planning turn; `proposal_iteration.py` owns saved
snapshots, exact issue/option responses, preservation, defer, and destination
changes; `proposal_projection.py` supplies the read-only workbench model; and
`apply.py` owns exact reviewed Apply routing and receipt validation.
`application.py` remains the current final-phase adapter while the later
candidate/Audit/Update loop is introduced. This relocation names the intended
pipeline without claiming that the later semantic pipeline is already built.

`runtime/source_access.py` is the sole implementation owner for loading the
exact frozen Meld Source/Target shapes and revalidating their names, UIDs, and
digests. `runtime/session_repository.py` owns durable proposal-session CAS,
preservation, defer, and destination relocation; provider/cache continuation
remains in `runtime/proposal_iteration.py`. The console command retains its
historical private helper names only
as direct aliases to those application-runtime functions. Session-picker and
explicit CLI resumes may perform an early recheck for prompt feedback, but
assessment publication and Apply repeat the same canonical checks at their
transaction boundary; the adapter does not maintain a parallel stale-binding
rule.

Exhaustive peer judgment is not owned by Meld or Compare. The relation model,
evidence projection, provider execution, and compatible repositories live in
`application.capabilities.memory_issue_analysis.peer_relations`. Meld imports
that capability through `MemoryRelation*` names and owns only the conversion
to Meld dispositions, issues, proposals, follow-up turns, and application.
The serialized `comparison_seed` and Study prewarm vocabulary remain intact so
existing sessions and prepared artifacts require no migration.

The historical flat `memcommit.meld_*_application`,
`memcommit.meld_application_flow`, and `memcommit.meld_runtime` paths retain
their existing compatibility policy. Importing
`memcommit.application.operations.meld` alone remains lazy. New production
consumers use the responsibility-named canonical paths; compatibility aliases
are not alternate implementation owners.

The 2026-08-30 pipeline-naming relocation removes the internal Start,
Restart, Assessment, Session, and Resolution file taxonomy. It does not change
request values, serialized session schemas, provider prompts, cache keys,
review interaction, or Apply behavior. `candidate_context` and
`integration_plan` become real model owners only when the later virtual
Context/Audit/Update loop supplies those values; empty predictive modules are
an intentional non-goal of this physical move.

The original relocation changed physical ownership only. The 2026-08-30
relation-first completion subsequently changed Start semantics: every new Meld
now consumes one shared Memory Relation Analysis before mode-specific
materialization. It leaves command grammar, TUI interaction, Apply,
checkpoints, recovery, and receipt presentation unchanged, so existing PTY
interaction evidence remains representative.
Provider decoding, resolution-cache persistence, saved choice branches, and
TUI presentation are intentionally unchanged. The pure common-Resolution
projection is now named `resolution_projection.py`; this is a mechanical name
change, not a new resolution workflow.

The subsequent relation-ownership pass makes `MemoryRelation*` the concrete
Python model/execution/repository definitions and leaves `Comparison*` as
identity aliases. Meld has no import edge to the Compare operation, its console
presentation, or its legacy prewarm module. Compare supplies only its own thin
presentation wrapper and command lifecycle; the shared detailed presenter
lives under `terminal.components.peer_relations`. Persisted directories,
provider operation labels, Study artifact keys, and Meld's JSON
`comparison_seed` remain unchanged. This pass does not add the deferred
Audit–Resolve–Update loop.

## Post-TUI completion audit (2026-08-15)

The original application extraction is real: assessment publication, saved
session CAS, restart replacement, destination relocation, and all four Apply
routes already execute outside `commands.meld`. The TUI relocation exposed a
narrower remaining problem, however: the CLI still prepares the initial
semantic basis before it calls that application boundary. Treating the earlier
matrix as fully closed would therefore hide adapter drift.

| Remaining boundary | Current command-owned behavior | Required terminal-independent result |
| --- | --- | --- |
| Start scope | direct-Memory selectors are parsed and used in a provisional directional session but are absent from `MeldStartRequest` | selectors are typed request fields, validated against descendant reach, and preserved in the durable session |
| Relation basis | symmetric relation creation and directional exact/equivalent/projected lookup occur in application runtime | one application/runtime resolver consumes shared Memory Issue Analysis, installation, provider fallback, and origin |
| Provider prediction | the CLI constructs a provisional session and repeats prewarm lookup to decide whether to open a progress surface | a typed prepared Start/Restart value reports whether semantic provider work remains without publishing state |
| Adapter parity | Python and agent Start enter the runtime without the CLI's Compare-preparation path | CLI, Python, and agent requests enter the same Prepare/Execute path and expose the same scope controls |

Progress: all four audited Start boundaries are now closed. Direct-Memory
scope is typed; ordered relation resolution is runtime-owned; and Start/Restart
first return a `PreparedMeldExecution` whose `provider_required` flag and
provisional read-only view come from the same frozen cache decision that is
later executed. Shared relation execution lives under the operation-neutral
Memory Issue Analysis capability; historical Compare vocabulary remains only
where persisted compatibility requires it.

The completion pass preserved the already extracted session and Apply services,
removed only the start-time parallel decisions, and proved that command code
contains no semantic cache lookup, provisional `MeldSession` construction,
provider decoder, session publication, or Apply transaction.

## Operation routes

| Route | Application contract | Production runtime | Public Python | Agent action | CLI |
| --- | --- | --- | --- | --- | --- |
| New directional review | `MeldStartRequest` | source/Grant checks, required peer-relation reuse or creation, relation-bound directional prewarm/materialization, session publication | `start_meld(mode="directional")` | `start` | positional/`--into`/`--from` normalize to the same request |
| New symmetric review | `MeldStartRequest` | source/transfer checks, exact ordered relation analysis, empty Result, atomic new target plus session when requested | `start_meld(mode="symmetric")` | `start` | current Result or `--to`; a prior Compare artifact may supply the shared relation basis |
| Replace saved review | `MeldRestartRequest` with opaque expected version | fail stale before provider, then share relation analysis, materialization/cache construction, and CAS-replace the session | `restart_meld` | `restart` | `--restart` |
| Open saved review | `MeldSessionRepository.load` | target UID lookup and canonical-digest version | `open_meld` | `open` | direct resume or saved-session picker |
| Semantic follow-up | `MeldResolutionTurnRequest`, common `ResolutionCase`, then `FrozenMeldAssessment` | exact saved version and issue/option UID validation, operation-owned guidance composition, cache replay or provider/repair, source/target revalidation, session CAS | `comment_meld(..., expected_version=...)` | `comment` requires version returned by `open` | visible issue ordinal is translated once to exact UID; TUI response actions already emit UID |
| Preserve remaining distinctions | `MeldPreservationRequest` | exact saved version; provider-free current symmetric schema; legacy/directional sessions use the ordinary assessment boundary | `preserve_meld(..., expected_version=...)` | `preserve` requires version | `--preserve-all` or TUI action |
| Defer review | `MeldSessionSnapshot` | exact saved version, provider-free session transition, and CAS | `defer_meld(..., expected_version=...)` | `defer` requires version | `--defer-all` or TUI action |
| Change symmetric destination | `MeldDestinationRequest` | empty-target validation and atomic Context/session relocation | not yet public | not yet exposed | TUI destination action |
| Apply decided assessment | `MeldApplyRequest` | exact decided version, complete local or Grant-owner transaction, recovery, checkpoint receipts, rollback, and session CAS | `apply_meld(..., expected_version=...)` | `apply` requires version | completion of required decisions or exact compatibility `--accept` |

## Cache matrix

| Semantic basis | Exact | Equivalent graph/scope | Safe subset projection | Provider construction on hit | Durable visible session before invocation |
| --- | --- | --- | --- | --- | --- |
| Peer relation analysis consumed by Meld | supported | supported where the declared relation proof matches | supported where the capability proves a complete requested projection | forbidden | no |
| Initial directional Meld review | supported | supported for the declared graph-equivalent scope | supported for a validated requested subtree/subset | forbidden | no |
| Meld follow-up resolution branch | exact full-request key | not inferred across different dialogue | not inferred across partial issue turns | forbidden | no |

Every lookup is performed only after the canonical Context names, descendant
reach, frozen Memories, authority, provider identity, request schema, and
operation version are known. A shared Study bundle remains immutable and is
referenced rather than copied into participant state. A validated shared hit is
promoted to the profile-local hidden cache; only the invoked operation may then
publish its ordinary target-bound session. Empty frames and zero-relation
results follow the same key and decoder rules rather than bypassing cache
validation.

## Invariants now enforced outside terminal code

- Directional source order is always `INCOMING, BASELINE`; the BASELINE is the
  target and remains authoritative.
- Symmetric source order is the exact saved relation-analysis order; the Result is
  distinct, local, empty, and session-free when starting.
- Source/target authority and frozen digests are rechecked before provider
  construction and again before durable publication where the operation spans
  a semantic turn.
- Ordered relation-analysis and Meld source projection exclude only process-local
  `authority-grant` QUERY navigation rows. Those rows carry no readable Memory
  content and do not widen descendant reach; persisted query references remain
  rejected rather than silently changing a source frame.
- Cache replay crosses the same strict decoder as a provider completion and
  cannot publish a partial assessment.
- Follow-up callers compose one `MeldResolutionTurnRequest`; its exact saved
  issue/option binding is validated by the common Resolution contract and
  translated to one operation-owned `MeldTurnRequest`, then all callers share
  `PreparedMeldTurnExecution`. Its cache decision, provider-required flag,
  repair path, and session CAS token are executed once by the runtime; CLI
  progress and public result projection do not assemble the lifecycle again.
- Meld's complete-ledger provider timeout is runtime-owned. CLI, Python, and
  agent calls therefore receive the same bound, including follow-up turns.
- Ordered peer-relation lookup and installation execute in `meld_runtime`:
  exact, equivalent-scope, and safe projected hits are resolved before a
  provider is constructed. Every Context-source miss invokes the shared live
  analysis and saves its durable ordered basis. Inline input retains the same
  typed basis only in its target-bound session because it has no source
  artifact locator. Directional materialization cannot return relation fields.
- Restart observes one opaque saved version before expensive work and replaces
  that exact version; it never deletes the prior review or creates a target.
- Every nonterminal saved-session mutation requires the version returned by
  `open`; stale comment, preserve, defer, and Apply requests stop before their
  provider/cache or mutation boundary.
- Apply never calls the provider and consumes only the exact decided session
  version. A repeated exact Apply may also name the reconstructable decided
  predecessor of the current APPLIED receipt; recovery must match its
  checkpoint and complete post-image and cannot publish another checkpoint.
- CLI Apply calls the same typed `execute_meld_apply` service as Python and
  agent adapters. It does not wrap that service in a second review/apply flow;
  route selection, CAS, recovery, rollback, and receipt validation remain in
  the operation boundary.
- `commands.meld` contains no target/session publication primitive. The CLI
  retains locator grammar, progress, rendering, and TUI orchestration. It also
  contains no ordered-relation cache lookup, directional prewarm lookup, or
  provisional `MeldSession` construction.

## Verification map

- Application contracts: `test_meld_start_application.py`,
  `test_meld_restart_application.py`, `test_meld_lifecycle_application.py`,
  `test_meld_resolution_application.py`, and `test_meld_application.py`.
- Runtime, CAS, cache, and boundary ownership: `test_meld_runtime.py`,
  `test_meld_provenance.py`, and `test_meld_application_flow.py`.
- Public and agent adapters: `test_meld_public_api.py`,
  `test_meld_agent_adapter.py`, and `test_agent_tool_registry.py`.
- CLI, saved sessions, and review UI compatibility: `test_meld.py`,
  `test_meld_sessions.py`, `test_meld_endpoint_setup.py`, and
  `test_meld_shell_directional.py`.
- Study exact/equivalent/projected reuse: `test_study_compare_graph_prewarm.py`
  and `test_study_meld_directional_exact_registry.py`.
- Grant-owner authority cases are additionally selected from
  `test_granted_impact.py` and `test_authority_grants.py`.

## Completion status

The interactive Meld screen and Endpoint Setup are now owned by
`interfaces.tui`; compatibility command paths are import-only. Session and
Apply execution are terminal-independent. Follow-up turns carry exact UIDs
through CLI, TUI, Python, and agent adapters into one operation-owned Resolution
preparer and then use one prepared cache/provider/CAS lifecycle. CLI Apply
enters the typed operation service directly. The final complete regression and
import-boundary pass closes this audit without introducing another session
schema or moving presentation.

On 2026-08-16, an isolated clean worktree passed 361 focused Meld, Study-cache,
registry, package, Resolution, semantic-policy, scope, and Grant tests. The
audit covered exact, equivalent, and projected cache hits without provider
construction; stale mutation rejection; all reviewed session actions; four
authority/storage shapes; zero-change and ordinary checkpoint recovery;
rollback; and Undo/Redo.

## 2026-08-20 execution-receipt migration

Meld's saved turns remain execution-owned judgments. Once the exact decided
session is applied, the command renders only effect/result counts, the session
and checkpoint identities, the post-application Review route, and recovery.
`mem review meld` rejects non-APPLIED sessions and cannot continue a Meld turn
or apply it. Staged sessions are resumed through `mem meld`.

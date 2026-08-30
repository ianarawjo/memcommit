# Sever application-boundary matrix

## Status

`VERIFIED` for the internal application and APPLY-01 boundary, reviewed
2026-08-25.

Sever is the second operation slice used to test the target application
architecture after Summarize. Its semantic analysis, private saved-session
lifecycle, execution-decision revisions, and self-/other-save Apply have typed,
terminal-independent entry points. Existing CLI setup, saved-session launching,
and Resolution presentation remain interface adapters and have not yet been
presented as a stable Python API.

## Motivation

Before this extraction, `memcommit.adapters.console.commands.sever.command` was the only complete
execution junction. Domain records, provider decoding, session persistence,
and review projection already had separate modules, but the command still
resolved authority, froze frames, consulted the Study cache, constructed the
provider, materialized the Result, and rendered terminal progress. A Python or
agent caller therefore had to invoke a CLI-shaped function or reproduce part of
the operation policy.

The extraction relocates that junction without changing the Sever meaning:

```text
CLI flags or TUI setup
        |
        v
SeverAnalysisRequest
        |
        v
run_sever_analysis
  | authority-frozen Source × Criteria
  | hidden prepared-analysis lookup
  | otherwise one whole-frame provider turn
        |
        v
SeverAnalysisResult(session, origin)
        |
        v
run_sever_session_start
        |
        v
SeverSessionSnapshot(session, opaque CAS token)
  | decision revision
  | destination revision
        |
        v
run_sever_session_apply
  | exact interrupted-Apply recovery
  | SELF-SAVE Source CAS or OTHER-SAVE require-new output + checkpoint
  | APPLIED-session CAS save
  | exact compensation if that save fails
        |
        v
SeverPersistedApplyResult
```

## Boundary matrix

| Concern | Typed/application owner | Production adapter | Existing interface adapter | Verified invariant |
| --- | --- | --- | --- | --- |
| Analysis input | `SeverAnalysisRequest` | `MemoryStoreSeverInputPort` | Positional roles, `--source`/`--from`, `--criteria`/`--against`, `--save-as`/`--to`, and three-pane setup map Source, Criteria, Result, and the two ranges | Duplicate role spellings fail before Store access; relative CLI locators are frozen to canonical public names before confirmation; runtime repeats authority checks before disclosure |
| Frozen evidence | `FrozenSeverInputs` | `capture_sever_binding` | No interface may append hidden Memories | Source and Criteria each retain exact Context identities, digests, ordinary Memories, Grant binding, range, and excluded query-only names |
| Cache | `SeverPreparedLookup` | installed Sever prewarm adapter | Interface receives the typed exact/equivalent/projected origin | Lookup runs only after authority and complete frame capture; a prepared decision ledger must exactly match the requested frozen bindings and output name after any adapter-owned safe projection |
| Provider | lazy `SeverProviderFactory` | configured provider supplied by the composition boundary | Progress is projected from typed stages | Cache hits never construct a provider; live work remains one whole-frame selective-curation turn |
| Decision result | `SeverAnalysisResult` | strict provider decoder or fresh prepared ledger | Resolution Workbench renders outstanding choices | The ledger covers every Source Memory exactly once and creates no Result Context |
| Session lifecycle | `SeverSessionRepository`, `SeverSessionSnapshot` | `MemoryStoreSeverSessionRepository` | launchers and `--resume` open a snapshot; interfaces never calculate a record digest | Create, load, and replace share one opaque optimistic-CAS contract |
| Decision revision | `SeverDecisionRequest` | repository replace under the snapshot token | scripted choices and TUI responses submit the same exact candidate UID and selection | stale revisions fail before they can overwrite a newer decision; custom content is valid only for `CUSTOM` |
| Destination revision | `SeverDestinationRequest`, `SeverDestinationPort` | live Store name validation plus repository CAS | the Save Location editor supplies only the proposed exact name | the exact ordinary local direct Source selects self-save; a fresh name selects other-save; every other existing or invalid output fails without rerunning analysis |
| Apply input | `SeverPersistedApplyRequest` | `MemoryStoreSeverOutputPort` plus the session repository | CLI `--accept` and TUI Accept call the same persisted use case | the current token is reloaded before any output effect; local frames and granted identity/revision/content are fresh at the Result commit point |
| Apply result | `SeverPersistedApplyResult` | Source CAS or require-new Context, checkpoint, APPLIED-session replacement, and exact compensation | interfaces receive the resulting snapshot | Source and Criteria bindings, candidates, save mode, output name, and grounded summary cannot change during Apply; a synchronous receipt failure publishes neither side |
| Interrupted Apply | same persisted request | exact Context/checkpoint recovery in `MemoryStoreSeverOutputPort` | retry uses the ordinary Apply path | only a self-save post-image or other-save Result whose digest and Sever checkpoint match the accepted session is adopted; unrelated state is never overwritten |
| Idempotence | `run_sever_session_apply` | output and repository ports are skipped for an already APPLIED snapshot | reopening an applied session remains read-only | a repeated application call creates no second mutation or session revision; exact interrupted recovery reports `created=False` |
| Presentation | none | none | command wait, plain renderer, setup TUI, Resolution Workbench | `operations.sever.application` imports no Typer, prompt-toolkit, TUI, or `commands.*` module |

## Dependency direction

`memcommit.application.operations.sever.model` owns the durable review vocabulary, exact
JSON validation, record digests, and Source/Criteria frame bindings.
`memcommit.application.operations.sever.provider` owns the operation-specific whole-frame
prompt and strict selective-curation decoder. Keeping these contracts separate
from `application` makes the application flow depend on validated Sever values
without making generic semantic execution or provider connection responsible
for Sever's decision meaning.

`memcommit.application.operations.sever.session_store` owns only the private session file
layout, locking, and digest CAS. Result materialization remains in
`memcommit.application.operations.sever.runtime`, because a private review receipt and an
ordinary Context mutation have different recovery and authority boundaries.
`memcommit.application.operations.sever.resolution_adapter` is the pure projection from a
validated session into shared Resolution values; keyboard, focus, rendering,
and terminal lifecycle remain under the interfaces and command layers.

`memcommit.application.operations.sever.application` therefore depends only on the
operation-owned model and provider-decoder contracts. It does not import
terminal or command modules. `memcommit.application.operations.sever.runtime` implements
Store, Grant, cache, provider-attempt, destination-validation, private-session,
and checkpoint ports. Grant mechanics temporarily remain under
`memcommit.application.capabilities.authority.context_access`; that transitional dependency is confined to the
runtime adapter, as it is for the Summarize slice.

The former flat `memcommit.sever`, `memcommit.sever_provider`,
`memcommit.sever_store`, `memcommit.sever_resolution_adapter`,
`memcommit.sever_application`, and `memcommit.sever_runtime` paths are
behavior-free module-identity aliases. They preserve old imports, monkeypatch
targets, and serialized globals while all production consumers import the
operation package directly. This is an ownership-only relocation: durable JSON,
whole-frame curation, authority, session CAS, Apply compensation, terminal
behavior, and the recorded TUI evidence are unchanged. No screenshot refresh
is required because no visible or interactive state changed.

`memcommit.adapters.console.commands.sever.command` retains thin `_start` and `_apply` compatibility
facades because existing internal tests historically called the analysis-only
and materialization-only paths. The executable command no longer calls the
session Store's `load` or `save`, calculates record digests, selects a candidate,
or changes an output name. Its CLI and TUI routes pass application-owned
snapshots and opaque version tokens to the runtime. New Study frame capture
imports the runtime owner directly rather than reaching through the command.

## Safety and compatibility invariants

- Analysis completes locator, READ/Grant, COMBINE, derived-transfer, retained-
  analysis, save-location, and complete-frame checks before cache lookup or
  provider construction.
- Query-only routes never disclose hidden content. Live `MemoryRef` values fail
  rather than being copied into a retained frame.
- Prepared and provider-produced decision ledgers cross the same validation gate;
  neither may change Source, Criteria, ranges, output name, or review state.
- Every durable decision mutation consumes the exact version token returned by
  create or open. The repository is the only layer that interprets that token
  as the current record digest.
- Apply reloads the durable snapshot before output creation. A stale REVIEWING
  or stale APPLIED snapshot fails before materialization; the final CAS catches
  a race that occurs after Result creation.
- Self-save updates one exact ordinary local Source root, preserving Context and
  retained Memory UIDs. Other-save creates a new local ordinary Context and
  leaves Source unchanged. Recursive and granted-Source self-save fail before
  provider construction.
- Local contributing Context digests remain the Store materializer's CAS set.
  Granted inputs revalidate the exact frozen Profile, Grant, permissions,
  public/resource mapping, and projected frame before and after creation while
  the registry is frozen. A stale/revoked Grant or changed authority Context
  fails without a partial Result.
- An all-KEEP review still records the reviewed application checkpoint in its
  selected save mode.
- If session receipt persistence raises, the adapter re-reads it before acting.
  A late committed receipt is success; an unchanged REVIEWING session triggers
  deletion of only the exact untouched other-save Result or restoration of the
  exact self-save pre-image; an indeterminate or changed state fails closed.
- Existing Sever session schema remains readable. Checkpoints now state
  `SELF_SAVE` or `OTHER_SAVE`; Undo/Redo restores the Context and session halves
  together in either mode.

## Verification evidence

The focused boundary and compatibility run currently covers:

- pure typed provider analysis and typed progress stages;
- prepared reuse with provider construction prohibited and its projection origin retained;
- rejection of a prepared review that changes the frozen Source or output;
- typed Apply receipt validation and idempotence;
- typed session create/open, decision, destination, persisted Apply, and stale-
  snapshot rejection;
- AST-level application independence from commands, Typer, and prompt-toolkit;
- runtime independence from Typer and prompt-toolkit;
- real-Store analysis with no terminal output or premature Result creation;
- real-Store self-save and other-save Apply, checkpoint creation, exact result
  content, Context/Memory identity preservation, and Source preservation in
  other-save;
- missing Source failure before provider construction;
- real-Store session CAS, destination validation, persisted Apply, and repeat-
  Apply idempotence without terminal output;
- existing CLI, TUI setup, authority, exact Study prewarm, review, Apply,
  Undo/Redo, and application-report behavior.
- local Source and Criteria freshness, Apply-time output-name races, all-KEEP
  materialization, self-/other-save synchronous compensation, and late-success
  detection;
- granted Source and Criteria success, authority-content changes, Grant
  revision and revocation, plus a change injected between the two Apply checks;
- exact interrupted-Apply recovery without a second mutation or Result identity;
- self-save provider-precondition rejection for recursive and granted Sources;
- self-save and other-save Undo/Redo with the saved session restored atomically.

The focused lifecycle, review-policy, restoration, local/granted boundary, and
compatibility tests pass. The ordered 180×52 true-color replay under
`agent-records/docs/screenshots/context-positional-grammar-20260821/` records Help, default
self-save, UID preservation, and explicit other-save. The older
`sever-apply-boundaries-20260815` set remains evidence for other-save
compensation and interrupted recovery.

## Remaining boundaries and non-goals

1. The complete known Result-created/session-REVIEWING gap is recoverable, but
   the prototype still has no cross-filesystem journal for storage damage below
   either atomic file primitive.
2. This boundary preserves `EXACT`, `EQUIVALENT_SCOPE`, and `PROJECTED` cache
   origins but does not decide when projection is safe. The Study prewarm
   adapter remains authoritative for that separate cache contract.
3. The setup workbench remains command-owned under
   `adapters.console.commands.sever`, while the operation-neutral Resolution
   Workbench remains shared. No Sever-specific `interfaces.tui.operations`
   package or compatibility facade remains.
4. The production private-session adapter still uses the existing POSIX
   `fcntl` lock. The repository contract is platform-neutral, but a Windows
   lock implementation remains part of the cross-platform infrastructure work.
5. The `execute_sever_*` functions are internal callable
   evidence, not a versioned public Python facade. Store-root ownership,
   configured-provider bootstrap, error taxonomy, and compatibility policy must
   be decided before public export.

## APPLY-01 case matrix

| Case | Expected effect | Verification |
| --- | --- | --- |
| Direct local Source and Criteria current; RESULT omitted/equal | Source Context UID retained; reviewed removals and transformations applied under retained Memory UIDs; one checkpoint | real Store and PTY receipt |
| Local Source and Criteria current; distinct fresh RESULT | New Result + one checkpoint; Source unchanged | real Store and PTY receipt |
| Granted Source current | OTHER-SAVE retains the same local Result behavior; SELF-SAVE fails before provider; no authority mutation | real Grant fixture |
| Granted Criteria current | The selected SELF-SAVE or OTHER-SAVE Source behavior; no Criteria-authority mutation | real Grant fixture |
| All candidates KEEP | SELF-SAVE retains Source identity/content and records the reviewed application; OTHER-SAVE publishes the complete derived Result | real Store and PTY receipt |
| Local Source or Criteria changes after review | Fail before Source update or new Result | parameterized CAS tests |
| Granted authority content changes after review | Fail before Source update or new Result | Source/Criteria role tests |
| Grant revised or revoked | Fail before Result | control-plane tests |
| Granted content changes during Result creation | Exact Result compensated; session REVIEWING | injected between-check test |
| Output name claimed after review | Existing owner untouched; session REVIEWING | require-new race test |
| Session receipt save fails before commit | SELF-SAVE restores the exact Source preimage; OTHER-SAVE removes the exact new Result/checkpoint | pure port + real Store + PTY |
| Session receipt commits then reports failure | Re-read as success; no compensation | pure port test |
| Process stops after exact Source update or Result/checkpoint | Retry adopts the exact application and saves the missing receipt | real Store + PTY recovery |
| Existing output is not the exact interrupted Result | Normal name collision; never adopted | require-new collision test |
| Already APPLIED retry | No new Context, checkpoint, or revision | persisted idempotence test |
| Close/cancel before Accept | REVIEWING session retained; no Result | workbench CLOSE test |
| Undo then Redo | SELF-SAVE Source state or whole OTHER-SAVE Result and matching receipt restored as one unit | command tests + PTY |

## 2026-08-20 execution-receipt migration

Sever decisions and Result creation are one execution lifecycle. APPLIED
success now prints a compact KEEP/FORGET receipt instead of the candidate
report. `mem review sever --session UID` accepts only an APPLIED session and
cannot decide candidates or materialize a Result; REVIEWING sessions resume
through `mem sever`.

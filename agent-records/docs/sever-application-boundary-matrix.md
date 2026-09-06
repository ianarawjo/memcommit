# Sever application-boundary matrix

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Status

`VERIFIED` for the internal application and APPLY-01 boundary, reviewed
2026-08-31.

Sever is the second operation slice used to test the target application
architecture after Summarize. Its semantic analysis, private saved-session
lifecycle, execution-decision revisions, and in-place Apply have typed,
terminal-independent entry points. Existing CLI setup, saved-session launching,
and Resolution presentation remain interface adapters and have not yet been
presented as a stable Python API.

## Motivation

Before this extraction, `memcommit.adapters.console.commands.sever.command` was the only complete
execution junction. Domain records, provider decoding, session persistence,
and review projection already had separate modules, but the command still
resolved authority, froze frames, consulted the Study cache, constructed the
provider, materialized the in-place after-state, and rendered terminal progress. A Python or
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
  | candidate-decision revision
        |
        v
run_sever_session_apply
  | exact interrupted-Apply recovery
  | reviewed choices -> owner-grouped UpdatePlans -> detached Context post-images
  | atomic in-place Source-owner CAS + per-owner checkpoints
  | APPLIED-session CAS save
  | exact compensation if that save fails
        |
        v
SeverPersistedApplyResult
```

## Boundary matrix

| Concern | Typed/application owner | Production adapter | Existing interface adapter | Verified invariant |
| --- | --- | --- | --- | --- |
| Analysis input | `SeverAnalysisRequest` | `MemoryStoreSeverInputPort` | Exactly two positional roles or `--source`/`--from` plus `--criteria`/`--against`; two-pane setup maps Source, Criteria, and independent ranges | Duplicate role spellings and any Result operand fail before Store access; relative CLI locators are frozen to canonical public names before confirmation; runtime repeats authority checks before disclosure |
| Frozen evidence | `FrozenSeverInputs` | `capture_sever_binding` | No interface may append hidden Memories | Source and Criteria each retain exact Context identities, digests, ordinary Memories, Grant binding, range, and excluded query-only names |
| Cache | `SeverPreparedLookup` | installed Sever prewarm adapter | Interface receives the typed exact/equivalent/projected origin | Lookup runs only after authority and complete frame capture; a prepared decision ledger must exactly match the requested frozen bindings and internal in-place Source identity after any adapter-owned safe projection |
| Provider | lazy `SeverProviderFactory` | configured provider supplied by the composition boundary | Progress is projected from typed stages | Cache hits never construct a provider; live work remains one whole-frame selective-curation turn |
| Decision result | `SeverAnalysisResult` | strict provider decoder or fresh prepared ledger | Resolution Workbench renders outstanding choices | The ledger covers every Source Memory exactly once and creates no Result Context |
| Session lifecycle | `SeverSessionRepository`, `SeverSessionSnapshot` | `MemoryStoreSeverSessionRepository` | launchers and `--resume` open a snapshot; interfaces never calculate a record digest | Create, load, and replace share one opaque optimistic-CAS contract |
| Decision revision | `SeverDecisionRequest` | repository replace under the snapshot token | scripted choices and TUI responses submit the same exact candidate UID and selection | stale revisions fail before they can overwrite a newer decision; custom content is valid only for `CUSTOM` |
| Destination revision | legacy `SeverDestinationRequest`, `SeverDestinationPort` | retained live Store name validation plus repository CAS | no Save Location is shown for new in-place sessions | destination revision remains only for reopening an older Result-bearing session; new console setup cannot create that shape |
| Apply input | `SeverPersistedApplyRequest` | `MemoryStoreSeverOutputPort` plus the session repository | CLI `--accept` and TUI Accept call the same persisted use case | the current token is reloaded before any Source effect; local frames and granted Criteria identity/revision/content are fresh at the commit point |
| Apply result | `SeverPersistedApplyResult` | owner-grouped Sever-to-`UpdatePlan` projection, detached `apply_update`, atomic Source-owner batch, per-owner checkpoints, APPLIED-session replacement, and exact compensation | interfaces receive the resulting snapshot | Source and Criteria bindings, candidates, owner set, and grounded summary cannot change during Apply; Update publishes nothing and a synchronous receipt failure publishes neither Sever side |
| Interrupted Apply | same persisted request | exact multi-owner Context/checkpoint recovery in `MemoryStoreSeverOutputPort` | retry uses the ordinary Apply path | only the complete in-place post-image set whose digests, membership, and Sever checkpoints match the accepted session is adopted; unrelated state is never overwritten |
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
layout, locking, and digest CAS. Sever-to-Update translation and Source
publication belong to `memcommit.application.operations.sever.apply`, because a private
review receipt and an ordinary Context mutation have different recovery and
authority boundaries. The deterministic in-memory ADD/EDIT/REMOVE projection
in `apply.projection` delegates to `memcommit.application.operations.update.application.apply_update`.
That shared boundary returns only detached post-images: it does not open an
Update workbench, persist an Update session, create a checkpoint, or render an
Update receipt. Sever therefore retains its save-mode, authority, recovery,
and publication meaning while no longer carrying a second local-update engine.
`memcommit.application.operations.sever.resolution_adapter` is the pure projection from a
validated session into shared Resolution values; keyboard, focus, rendering,
and terminal lifecycle remain under the interfaces and command layers.

`memcommit.application.operations.sever.application` therefore depends only on the
operation-owned model and provider-decoder contracts. It does not import
terminal or command modules. `memcommit.application.operations.sever.runtime` implements
Store, Grant, cache, provider-attempt, legacy-destination, private-session,
and checkpoint ports. Grant mechanics temporarily remain under
`memcommit.application.context_access.access`; that transitional dependency is confined to the
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

- Analysis completes locator, Source-locality, READ/Grant, retained-analysis,
  and complete-frame checks before cache lookup or provider construction.
- Query-only routes never disclose hidden content. Live `MemoryRef` values fail
  rather than being copied into a retained frame.
- Prepared and provider-produced decision ledgers cross the same validation gate;
  neither may change Source, Criteria, ranges, owner identity, or review state.
- Every durable decision mutation consumes the exact version token returned by
  create or open. The repository is the only layer that interprets that token
  as the current record digest.
- Apply reloads the durable snapshot before Source mutation. A stale REVIEWING
  or stale APPLIED snapshot fails before materialization; the final CAS catches
  a race that occurs after the Source-owner batch.
- In-place Apply updates every frozen ordinary local Source owner, preserving
  Context and retained Memory UIDs. Source and Criteria descendant ranges are
  independent. A granted Source fails before provider construction.
- Local contributing Context digests remain the Store materializer's CAS set.
  Granted inputs revalidate the exact frozen Profile, Grant, permissions,
  public/resource mapping, and projected frame before and after creation while
  the registry is frozen. A stale/revoked Grant or changed authority Context
  fails without a partial Source update.
- An all-KEEP review still records the reviewed grouped application checkpoint
  set.
- If session receipt persistence raises, the adapter re-reads it before acting.
  A late committed receipt is success; an unchanged REVIEWING session triggers
  restoration of every exact Source-owner pre-image; an indeterminate or
  changed state fails closed.
- Existing Sever session schema and old other-save receipts remain readable.
  New checkpoints carry complete owner membership; Undo/Redo restores all
  Context and session halves together as one command unit.

## Verification evidence

The focused boundary and compatibility run currently covers:

- pure typed provider analysis and typed progress stages;
- prepared reuse with provider construction prohibited and its projection origin retained;
- rejection of a prepared review that changes the frozen Source or output;
- typed Apply receipt validation and idempotence;
- typed session create/open, decision, persisted Apply, and stale-
  snapshot rejection;
- AST-level application independence from commands, Typer, and prompt-toolkit;
- runtime independence from Typer and prompt-toolkit;
- real-Store analysis with no terminal output or premature Source mutation;
- real-Store direct and descendant-inclusive in-place Apply, per-owner
  checkpoint creation, exact after-state content, and Context/Memory identity
  preservation; focused spies verify EDIT/REMOVE projection through the shared
  Update application boundary;
- missing Source failure before provider construction;
- real-Store session CAS, persisted Apply, and repeat-
  Apply idempotence without terminal output;
- existing CLI, TUI setup, authority, exact Study prewarm, review, Apply,
  Undo/Redo, and application-report behavior.
- local Source/Criteria freshness, Source-subtree membership races, all-KEEP
  materialization, multi-owner synchronous compensation, and late-success
  detection;
- granted Criteria success plus authority-content, revision, and revocation
  failures; granted Source rejection before provider construction;
- exact interrupted-Apply recovery without a second mutation;
- direct and descendant-inclusive in-place Undo/Redo with the saved session
  restored atomically; old other-save restoration remains covered as a
  compatibility route.

The focused lifecycle, review-policy, restoration, local/granted boundary, and
compatibility tests pass. The ordered 180×52 true-color replay under
`agent-records/docs/screenshots/sever-shared-endpoint-setup-20260823/` records
the current two-role setup, independent descendant controls, in-place Apply,
and owner-preserving verification. The older
`sever-apply-boundaries-20260815` set remains evidence for other-save
compatibility compensation and interrupted recovery.

## Remaining boundaries and non-goals

1. The complete known Source-batch/session-REVIEWING gap is recoverable, but
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
| Direct local Source and Criteria current | Source Context UID retained; reviewed removals and transformations applied under retained Memory UIDs; one checkpoint | real Store and PTY receipt |
| Source descendants included | Every frozen direct owner stays at the same name and UID; all owner checkpoints share one command membership | real Store, Undo/Redo, and PTY receipt |
| Source root only, Criteria descendants included | Only the Source root is mutable; the complete Criteria subtree remains one read-only criterion frame | independent-scope test |
| Granted Source selected | Fail before provider; no authority mutation | real Grant fixture |
| Granted Criteria current | Local Source owners update in place; no Criteria-authority mutation | real Grant fixture |
| All candidates KEEP | Source identities/content remain and the reviewed grouped application is recorded | real Store and PTY receipt |
| Local Source or Criteria changes after review | Fail before any Source update | parameterized CAS tests |
| Source subtree membership changes after review | Fail before any Source update | catalog-CAS test |
| Granted Criteria content changes, Grant revised, or Grant revoked | Fail before Source update | control-plane tests |
| Session receipt save fails before commit | Restore every exact Source-owner preimage and provisional checkpoint | pure port + real Store + PTY |
| Session receipt commits then reports failure | Re-read as success; no compensation | pure port test |
| Process stops after exact Source-owner batch | Retry adopts the complete exact application and saves the missing receipt | real Store + PTY recovery |
| Already APPLIED retry | No new Context, checkpoint, or revision | persisted idempotence test |
| Close/cancel before Accept | REVIEWING session retained; Source unchanged | workbench CLOSE test |
| Undo then Redo | Every Source owner state and matching per-owner receipt restored as one unit | command tests + PTY |

## 2026-08-20 execution-receipt migration

Sever decisions and in-place Source mutation are one execution lifecycle. APPLIED
success now prints a compact KEEP/FORGET receipt instead of the candidate
report. `mem review sever --session UID` accepts only an APPLIED session and
cannot decide candidates or mutate a Source; REVIEWING sessions resume
through `mem sever`.


## 2026-09-05 Apply module ownership

The internal Apply port is now implemented in `apply/execution.py`, with
`apply/projection.py` for detached results, `apply/checkpoints.py` for checkpoint
metadata and legacy matching, and `apply/self_save.py` / `apply/other_save.py`
for each mode's publication, recovery, and compensation. Shared input capture
lives in `inputs.py` so analysis and Apply revalidation do not depend on runtime
composition. `runtime.py` keeps callable entry points and behavior-free aliases
for its former input/output port and capture names.

The lifecycle and safety invariants above are unchanged. See the Apply
responsibility split in [the Sever rationale](mem-sever-design-rationale.md)
for the motivating scenario, dependency direction, naming decisions, and
remaining Store coupling. No new operation route state or UI behavior is
introduced by this module split.

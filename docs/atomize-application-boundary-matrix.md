# Atomize application-boundary matrix

## Status

`VERIFIED` for analysis open/create/reuse, local in-place structural Apply, and
their bounded public Python projection; reviewed 2026-08-15.

This note records the first two Atomize application slices. Analysis
open/create/reuse and local in-place Apply now cross typed,
interface-independent boundaries. They preserve Atomize semantics, provider
prompts, Study fixtures, saved schemas, and ordinary TUI navigation while
making saved reuse, hidden-prewarm materialization, provider creation, and
structural application independently callable. The public projection exposes
analysis plus in-place `Apply as is`; the require-new save-as route remains an
internal reviewed lifecycle and is not part of that stable public contract.

## Current execution junction

Atomize already separated its semantic records, strict provider decoder,
mutable workbench model, and presentation. Analysis open, in-place Apply, and
Save As now have distinct application/runtime junctions; the stable Python
surface deliberately exports only the first two:

```text
CLI flags or TUI action
        |
        v
load exact local Context
        |
        v
AtomizeAnalysisOpenRequest
        |
        +-- exact current saved pair --> SAVED
        +-- allowed hidden Study hit --> EXACT_PREWARM
        `-- otherwise --> lazy provider construction --> PROVIDER
        |
        v
durable analysis/workbench pair + typed origin
        |
        v
command-owned semantic/review gates
        |
        +-- in place --> AtomizeSessionSnapshot
        |                + exact analysis/workbench revision
        |                + recover or create one atomize checkpoint
        |                + CAS-save terminal receipt
        |                + compensate an uncommitted exact checkpoint
        |
        `-- save-as  --> create source copy + init checkpoint
                        + atomize checkpoint + current switch
        |
        v
typed Apply result or retained save-as state
        |
        v
render command receipt
```

`memcommit.atomize_application` owns the in-place lifecycle and imports no
terminal adapter or Store. `memcommit.atomize_runtime` owns the Store session
repository, strict graph preflight, checkpoint reconstruction, materialization,
and compensation. The Context/checkpoint and workbench receipt remain separate
atomic files, but the application result treats them as one synchronous
outcome: it re-reads late success, compensates an uncommitted new checkpoint,
and recovers an exact previously interrupted checkpoint without replaying the
transformation.

`memcommit.atomize_analysis_application` owns the open request/result, origin
contract, and result validation without importing Store, commands, Typer, or
prompt-toolkit. `memcommit.atomize_analysis_runtime` owns saved-pair lookup,
hidden-prewarm lookup, lazy provider connection, Context freshness recheck,
pair publication, and the existing synchronous restoration path. The legacy
`atomize_workflow` module is now a compatibility facade over that boundary.

## Operation-owned decisions to preserve

- Atomize applies exactly one immutable semantic analysis identity at most
  once. Undo, later edits, or loss of a derived Output do not rearm it.
- `COMPOSITE` replaces one source occurrence in place with fresh child UIDs.
  `ATOMIC`, `UNCERTAIN`, and `NON_PROPOSITIONAL` preserve source UID and text.
- Open optional Ambiguity, Atomize Uncertainty, and Conflict findings do not
  become implicit answers. Applying the exact proposal records `AS_IS` and a
  bounded unresolved-finding audit in the checkpoint.
- A saved eligible unary response must be incorporated through one complete
  semantic turn before structural Apply. Pair-shaped conflict responses remain
  review evidence and are not converted to unary source frames.
- An all-preserved analysis is a deliberate recorded completion: it creates an
  Atomize checkpoint and terminal receipt even though Context Memory bytes do
  not change. This differs from Update's zero-operation receipt-only no-op and
  from Sever's all-KEEP require-new Result.
- In-place splitting is blocked when an inbound `MemoryRef` targets a source
  that would disappear. Save-as leaves the source identity intact and therefore
  permits the same reference.
- Save-as publishes a fresh Context identity before its later phases. Once
  published, a failure preserves that Context for inspection because another
  process may already have observed or referenced it. This is an intentional
  non-destructive recovery boundary, not exception atomicity.
- A legacy analysis-only route can apply without a workbench. Its checkpoint
  is the one-shot evidence; a Source-owned terminal workbench receipt exists
  only when a workbench existed before Apply.
- Atomize currently accepts local ordinary Contexts. Grant-aware readable
  Source and authority-owned mutation are not silently inferred from picker
  visibility and are not part of this application slice.

## APPLY-01 case matrix

| Case | Current effect | Evidence state | Extraction requirement |
| --- | --- | --- | --- |
| Preview or workbench open | Analysis/workbench artifacts only; no Context checkpoint | existing preview, workbench, and Study-prewarm tests | typed analysis result must remain non-applying |
| Close/cancel before final action | Saved review may remain; no Context effect | shared Resolution CLOSE and workbench persistence tests | application port must never be called |
| Local current analysis, one or more splits | one in-place Context checkpoint, complete SPLIT/KEEP/PRESERVE trace | `test_saved_atomize_analysis_applies_once_with_recorded_lineage` | consume exact analysis and workbench revision |
| Every item preserved | one no-change Atomize checkpoint and terminal receipt | `test_all_atomic_apply_records_a_deliberate_no_change_checkpoint` | preserve this explicit Atomize no-op variant |
| Open optional findings | exact current proposal applies; checkpoint records `AS_IS` and open findings | `test_unanswered_atomize_findings_apply_as_is_and_are_checkpointed` | silence must remain `OPEN`, never an inferred choice |
| Eligible unary response not incorporated | fail before Context mutation | workbench response/save-gate tests | retain exact response-digest gate |
| Compound incorporate-and-apply | one provider reanalysis, then ordinary Apply path | compound workbench action test | one typed request must carry both reviewed revision and apply intent |
| Pair-shaped conflict response | cannot enter unary reanalysis; current structural proposal remains independently applicable | mixed pairwise-response tests | keep conflict semantics outside Atomize transformation |
| Source Context changed after analysis | fail stale before Apply | stale analysis tests | revalidate exact local identity, digest, direct order, and content |
| Embedded Context unavailable | fail before saving parent | embedded-Context safety test | mutating load must stay complete |
| Inbound reference to split source | fail before mutation | inbound-reference test | strict graph scan remains a preflight |
| Repeated exact Apply | no second checkpoint or effect | lineage/idempotence tests | terminal receipt or exact checkpoint recovery must make retry idempotent |
| Undo then retry | In-place Apply can return to old bytes while remaining terminal; Save As lifecycle Undo removes its created Context and reverses its Source receipt | Undo/retry and Save As lifecycle tests | do not equate byte equality with application eligibility; creation Undo is an explicit whole-command reversal |
| Destination occupied or raced | unrelated Context is never overwritten | save-as collision/race tests | require-new publication remains authoritative |
| Save-as succeeds | Source unchanged; transform finishes before publication; destination gets one final Atomize creation checkpoint, analysis copy, Source receipt, then conditional current switch | save-as lineage and lifecycle tests | return one typed complete-effect receipt |
| Save-as fails before publication | no destination or destination analysis remains | injected transform/publication tests | hidden preparation is not a visible command state |
| Save-as fails after publication | exact final destination is retained and retry finishes the missing receipt/selection without another checkpoint | receipt- and switch-failure retry tests | distinguish retained recoverable publication from success |
| Terminal receipt write fails before commit | exact new checkpoint is removed and the exact pre-Apply Context record is restored | compensation boundary test | verified for synchronous local failure |
| Terminal receipt commits then reports failure | exact terminal workbench is re-read and reported as success | late-success boundary test | verified under the session lock and application re-read |
| Retry after checkpoint but before terminal receipt | exact trace/audit/checkpoint is adopted, receipt is repaired, and no duplicate checkpoint is created | interrupted recovery test | verified even after later Context edits because recovery never overwrites current content |
| Workbench changes after Context save | exact new Context/checkpoint effect is compensated; the newer review remains nonterminal | injected CAS-race test | verified against the complete opaque workbench revision |

## EFFECT-01 case matrix

| Route | Durable writes | Current Undo/Redo unit | Required decision |
| --- | --- | --- | --- |
| Analysis-only | latest analysis and optional workbench | not a Context history effect | application session lifecycle only |
| In-place structural Apply | one Context replacement, one Atomize checkpoint, optional terminal workbench receipt | one `mem undo` / `mem redo` restores the whole Context snapshot; session remains terminal | verified, including receipt compensation and interrupted recovery |
| All-preserved in-place Apply | same checkpoint/receipt with unchanged Memory ledger | Undo/Redo records history although Memory content is unchanged | preserve as explicit completion, not collapse to Update semantics |
| Save-as structural Apply | new Context, init checkpoint, copied analysis, Atomize checkpoint, current-pointer CAS, Source terminal receipt | one Undo reverses only the Atomize checkpoint to the created baseline; it does not remove the new Context | either define a compound operation unit or document this as an intentional two-checkpoint exception before verification |
| Save-as failure after publication | inspectable new Context in its last durable phase; Source unchanged | manual inspection/recovery; no complete success receipt | add a typed partial-publication result and exact retry/adoption rules |
| Structural Apply receipt failure | synchronous pre-commit failure exposes no Context effect; a prior exact checkpoint is recoverable without replay | checkpoint/receipt pair remains one application outcome | verified for local in-place Apply |
| Grounding proposal Apply | separate edit/add transaction and grounding receipt/history | already has exact checkpoint recovery and mixed-write rollback tests | do not merge its schema with structural Atomize; reuse only the application/recovery mechanics |

## Hidden prewarm and visible-session boundary

The Study Atomize prewarm is a hidden declared artifact, not a pre-created user
session. Initialization validates and installs only its hidden entry receipt.
The first explicit matching Atomize invocation materializes the prepared
analysis through the ordinary production slot and creates a blank run-local
workbench. A mismatch, stale Source, configuration mismatch, or failed
workbench publication must not expose a partial visible session or connect a
provider under the guise of a hit.

This cache boundary is adjacent to Apply but independent from it. The
application API returns the typed origin `SAVED`, `EXACT_PREWARM`, or
`PROVIDER`. `allow_prepared` is an operation-owned request policy: Impact
refresh/review prohibit hidden reuse, while ordinary first use may allow it.
The runtime, not the command, looks up the artifact only
after the exact Context has been loaded and before constructing a provider.
Hidden installation files remain outside the public session repository, and a
cache hit does not bypass later Apply freshness or authority checks.

## Implemented and remaining extraction boundary

The in-place slice preserves the current domain records and adds this typed
lifecycle:

```text
AtomizeSessionSnapshot(analysis, workbench, opaque revision)
        -> AtomizePersistedApplyRequest
        -> run_atomize_session_apply
        -> AtomizePersistedApplyResult
             + exact checkpoint/result
             + terminal snapshot when a workbench exists
             + created/recovered disposition
```

Suggested ownership:

- `memcommit.atomize_application`: implemented typed requests/results,
  lifecycle ordering, idempotence, audit projection, and port protocols; no
  Typer, prompt-toolkit, Store paths, or Study fixture imports.
- `memcommit.atomize_runtime`: local Context capture, strict graph preflight,
  session repository, Context materialization, compensation, and
  interrupted-Apply recovery.
- `memcommit.atomize_analysis_application`: implemented typed analysis-open
  request/result, exact origin validation, and terminal-independent port.
- `memcommit.atomize_analysis_runtime`: saved-pair and hidden-prewarm lookup,
  lazy provider analysis, freshness recheck, and pair publication/restoration.
- `memcommit.commands.atomize`: CLI/TUI composition, progress and receipts,
  mapping final workbench actions to the typed in-place or Save As use case;
  the command retains presentation policy but not either materialization
  lifecycle.
- existing `memcommit.atomize`, `atomize_workbench`, and grounding modules:
  semantic/domain records and their operation-specific validation; schemas are
  not merged merely because lifecycle mechanics become common.

The opaque session revision binds the immutable analysis record and complete
workbench record, including response state, Output plan, and any application
receipt. Every ordinary analysis/workbench writer shares one Context-scoped
session lock; the repository rechecks the token before terminal publication.

## Ordered implementation gates

1. **Done:** add pure request/result/port types and prove that the application
   and runtime modules have no command, Typer, or prompt-toolkit dependency.
2. **Done:** wrap the saved analysis/workbench pair in an opaque repository
   snapshot without exposing record digests to CLI or TUI adapters.
3. **Done:** route local in-place Apply through that snapshot; close
   compensation, late-success, interrupted-recovery, later-edit, and
   workbench-race cases.
4. **Done:** move open/create/reuse behind an analysis application use case
   while retaining exact hidden-prewarm and provider-free resume behavior.
5. **Done:** route save-as through a typed request/result, publish one final
   creation checkpoint, retain exact post-publication failures for idempotent
   retry, and restore Context/analysis/receipt as one Undo/Redo lifecycle.
6. **Partial:** the stable Python projection now opens the exact durable pair
   and applies in place; move the remaining shared Resolution/save-as actions
   to independently reviewed typed public use cases before exporting them.
7. **Done:** make new save-as histories one Atomize creation unit; leave
   pre-release legacy `init + atomize` histories uninterpreted.

## Current verification evidence

The current Atomize-focused run passes 186 tests with one pre-existing
grounding screen-capture comparison deselected because its expected wording no
longer matches the shared renderer. The new six-case analysis-boundary file
directly covers provider creation, provider-free saved resume, exact
hidden-prewarm materialization, prepared-reuse policy, stale rejection,
refresh, and module dependency direction; the existing refresh rollback test
continues to prove analysis/workbench pair restoration. The structural boundary
file passes eleven cases: recorded all-preserved completion, in-place receipt
compensation, late-success detection, interrupted recovery, later-edit
preservation, workbench-race compensation, dependency direction, final-only
Save As, creation-lifecycle Undo/Redo, prepublication failure cleanup, exact
receipt retry, and recorded Source-frame lineage for both KEEP and SPLIT. A
second integrated run passes 202 command, Context safety, history/restoration,
write-protection, and Study-installation tests.

The existing screenshot sets cover Study hidden-session initialization, exact
prewarm entry, split review, final approval/application, output verification,
accumulated editing, Memory selection, and Undo history. They are useful
behavioral evidence. The focused
[180×52 in-place Apply replay](screenshots/atomize-apply-boundaries-20260815/README.md)
adds eight ordered true-color captures for review, normal application,
read-only verification, receipt compensation, late success, interrupted
checkpoint recovery, recovery verification, and workbench-CAS compensation;
an ordinary success screenshot alone is not treated as proof of those
boundaries.

The focused
[180×52 Save As command-unit replay](screenshots/atomize-save-as-command-unit-20260815/README.md)
adds eight ordered color-PTY captures for exact location review, final-only
publication, read-only lineage, one-command Undo/Redo, prepublication failure,
retained output, and exact retry recovery.

The focused
[180×52 analysis-open replay](screenshots/atomize-analysis-open-boundary-20260815/README.md)
adds eleven ordered true-color captures for provider progress and publication,
provider-free saved resume, exact hidden-prewarm first materialization,
explicit refresh, stale rejection, and analysis/workbench pair restoration.

## Non-goals of this slice

- no provider-prompt or Atomize classification change;
- no migration of the in-progress exact-Memory selection work;
- no change to `APPLY`, `APPLY AS IS`, or ownership-aware presentation policy;
- no deletion or cleanup of a published save-as destination;
- no change yet to save-as partial-publication or Undo semantics;
- no unification of structural Atomize and grounding-proposal schemas;
- no claim that workbench response editing, compound reanalysis, or structural
  Save As is a stable public Python API; the bounded analysis-open and in-place
  `Apply as is` contract is recorded separately in
  `atomize-public-python-api-design-rationale.md`.

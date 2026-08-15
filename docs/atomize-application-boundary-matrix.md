# Atomize application-boundary matrix

## Status

`CHARACTERIZED`, not `VERIFIED`, for `APPLY-01` and `EFFECT-01`, reviewed
2026-08-15.

This note is the preparation gate before Atomize is moved behind an
interface-independent application boundary. It records the current structural
Atomize behavior, the operation-owned differences that must survive, and the
known failure/recovery gaps that the extraction must close. It does not change
Atomize semantics, provider prompts, Study fixtures, saved schemas, or TUI
navigation.

## Current execution junction

Atomize already separates its semantic records, strict provider decoder,
mutable workbench model, and presentation. The complete lifecycle still joins
inside `memcommit.commands.atomize`:

```text
CLI flags or TUI action
        |
        v
load local Context + latest analysis/workbench
        |
        +-- first use --> hidden Study lookup or provider analysis
        |
        +-- review responses --> optional complete reanalysis
        |
        v
command-owned freshness and safety checks
        |
        +-- in place --> mutate Context + one atomize checkpoint
        |
        `-- save-as  --> create source copy + init checkpoint
                        + atomize checkpoint + current switch
        |
        v
save Source-owned terminal workbench receipt
        |
        v
render command receipt
```

The final workbench-receipt write is outside the Context/checkpoint write. A
Python or agent caller therefore cannot execute the complete operation without
calling command-owned policy, and an exception between those writes can leave
the durable effect and the terminal session state disagreeing.

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
| Undo then retry | Context can return to its old bytes, but the analysis remains terminal | Undo/retry test | do not equate byte equality with application eligibility |
| Destination occupied or raced | unrelated Context is never overwritten | save-as collision/race tests | require-new publication remains authoritative |
| Save-as succeeds | Source unchanged; destination gets init baseline, atomize checkpoint, analysis copy, then conditional current switch | save-as lineage test | return one typed complete-effect receipt |
| Save-as fails after publication | published destination is retained for manual inspection | published-failure and switch-failure tests | result must explicitly distinguish retained partial publication from success |
| Terminal receipt write fails before commit | Context/checkpoint currently remain while workbench stays nonterminal | strict xfail boundary test | compensate exact effect or recover it atomically before returning failure |
| Terminal receipt commits then reports failure | durable success currently returns a command error | strict xfail boundary test | re-read exact receipt and report success |
| Retry after checkpoint but before terminal receipt | retry reports already applied but does not repair workbench | strict xfail boundary test | adopt only the exact matching checkpoint and persist the missing receipt |

## EFFECT-01 case matrix

| Route | Durable writes | Current Undo/Redo unit | Required decision |
| --- | --- | --- | --- |
| Analysis-only | latest analysis and optional workbench | not a Context history effect | application session lifecycle only |
| In-place structural Apply | one Context replacement, one Atomize checkpoint, optional terminal workbench receipt | one `mem undo` / `mem redo` restores the whole Context snapshot; session remains terminal | close receipt compensation and interrupted recovery |
| All-preserved in-place Apply | same checkpoint/receipt with unchanged Memory ledger | Undo/Redo records history although Memory content is unchanged | preserve as explicit completion, not collapse to Update semantics |
| Save-as structural Apply | new Context, init checkpoint, copied analysis, Atomize checkpoint, current-pointer CAS, Source terminal receipt | one Undo reverses only the Atomize checkpoint to the created baseline; it does not remove the new Context | either define a compound operation unit or document this as an intentional two-checkpoint exception before verification |
| Save-as failure after publication | inspectable new Context in its last durable phase; Source unchanged | manual inspection/recovery; no complete success receipt | add a typed partial-publication result and exact retry/adoption rules |
| Structural Apply receipt failure | Context effect may exist without terminal workbench state | checkpoint prevents duplicate mutation but does not repair the session | exact compensation, late-success detection, and recovery are required |
| Grounding proposal Apply | separate edit/add transaction and grounding receipt/history | already has exact checkpoint recovery and mixed-write rollback tests | do not merge its schema with structural Atomize; reuse only the application/recovery mechanics |

## Hidden prewarm and visible-session boundary

The Study Atomize prewarm is a hidden declared artifact, not a pre-created user
session. Initialization validates and installs only its hidden entry receipt.
The first explicit matching Atomize invocation materializes the prepared
analysis through the ordinary production slot and creates a blank run-local
workbench. A mismatch, stale Source, configuration mismatch, or failed
workbench publication must not expose a partial visible session or connect a
provider under the guise of a hit.

This cache boundary is adjacent to Apply but independent from it. The future
application API should receive a typed analysis origin such as `PREPARED` or
`LIVE`; it must not make hidden installation files part of the public session
repository or allow a cache hit to bypass Apply freshness and authority checks.

## Target extraction boundary

The first implementation should preserve the current domain records and add a
thin typed lifecycle around them:

```text
AtomizeAnalysisRequest
        -> run_atomize_analysis
        -> AtomizeAnalysisResult(analysis, origin)

AtomizeSessionSnapshot(analysis, workbench, opaque revision)
        -> revise destination / responses
        -> refreshed AtomizeSessionSnapshot

AtomizePersistedApplyRequest(snapshot, route)
        -> run_atomize_session_apply
        -> APPLIED | RETAINED_PARTIAL AtomizeApplyReceipt
```

Suggested ownership:

- `memcommit.atomize_application`: typed requests/results, lifecycle ordering,
  idempotence, and port protocols; no Typer, prompt-toolkit, Store paths, or
  Study fixture imports.
- `memcommit.atomize_runtime`: local Context capture, strict graph preflight,
  hidden prepared lookup, provider construction, session repository, Context
  materialization, compensation, and interrupted-Apply recovery.
- `memcommit.commands.atomize`: CLI/TUI composition, progress and receipts,
  mapping final workbench actions to the typed use cases.
- existing `memcommit.atomize`, `atomize_workbench`, and grounding modules:
  semantic/domain records and their operation-specific validation; schemas are
  not merged merely because lifecycle mechanics become common.

The opaque session revision must bind at least the immutable analysis UID, the
complete workbench record (including response state and Output plan), and its
application receipt. The command currently compares identity at several
points but has no one token spanning approval through terminal publication.

## Ordered implementation gates

1. Add pure request/result/port types and prove that the application module has
   no command, Typer, prompt-toolkit, or filesystem dependency.
2. Move open/create/reuse behind an analysis application use case while
   retaining exact hidden-prewarm and provider-free resume behavior.
3. Wrap the saved analysis/workbench pair in an opaque repository snapshot;
   do not expose record digests to CLI or TUI adapters.
4. Route in-place Apply through that snapshot and close the three strict-xfail
   receipt/recovery cases before calling the slice verified.
5. Characterize workbench changes racing final approval and require exact CAS
   before and after Context publication.
6. Give save-as an explicit typed partial-publication result and choose its
   Undo model without deleting a possibly observed Context by name.
7. Rewire CLI and shared Resolution actions to the typed use cases, then remove
   duplicated command-owned policy.
8. Run existing Atomize, authority/write-protection, history/restoration,
   Study-prewarm, and shared Resolution suites plus an ordered 180×52 PTY path
   covering entry, review/as-is, final action, receipt, verification, Undo,
   Redo, receipt failure, and recovery.

## Current verification evidence

The existing Atomize-focused collection contains 174 tests. On the current
worktree, 173 pass and one pre-existing grounding screen-capture comparison
fails because its expected wording no longer matches the shared renderer. The
new structural boundary file adds one passing no-change case and three strict
expected failures for the unimplemented receipt/recovery guarantees.

The existing screenshot sets cover Study hidden-session initialization, exact
prewarm entry, split review, final approval/application, output verification,
accumulated editing, Memory selection, and Undo history. They are useful
behavioral evidence but do not prove the three missing failure/recovery cases;
new PTY captures belong with the implementation that closes those cases.

## Non-goals of this preparation

- no provider-prompt or Atomize classification change;
- no migration of the in-progress exact-Memory selection work;
- no change to `APPLY`, `APPLY AS IS`, or ownership-aware presentation policy;
- no deletion or cleanup of a published save-as destination;
- no unification of structural Atomize and grounding-proposal schemas;
- no claim that Atomize is a stable public Python API yet.

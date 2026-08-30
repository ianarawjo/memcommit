# Atomize application-boundary matrix

## 2026-08-29 responsibility revision

The current Atomize application boundary includes analysis open/reuse, exact
Output planning, in-place structural Apply, require-new Save As, complete
unresolved-issue receipt, and provider-free read-only Review. Response edits,
response reanalysis, compound incorporation, and executable Atomize Grounding
are removed. Findings remain immutable evidence and
`ATOMIZE_UNCERTAINTY` is presented externally as `AMBIGUITY`.

Legacy workbench response fields remain serialized but unused. Grounding
models, Store paths, retained-history validation, Context cleanup, and
companion Undo/Redo restoration are removed; historical Context snapshots use
only the common reconstruction and restoration paths.

The response/reanalysis/Grounding rows later in this document are retained as
historical extraction evidence and are superseded by
[`atomize-read-only-findings-design-rationale.md`](atomize-read-only-findings-design-rationale.md).
Current callable-boundary tests and the operation catalog must contain only
open, Output planning, Apply as-is, and Save As.

## Status

`VERIFIED` for analysis open/create/reuse, exact Output planning, local in-place
Apply, require-new Save As, complete unresolved receipt, read-only Review, and
their public Python/agent projection; reviewed 2026-08-29.

Analysis, Output planning, and both materialization directions cross typed,
interface-independent boundaries. They preserve Atomize prompts,
classifications, Study fixtures, saved schemas, and ordinary TUI navigation.
The stable public projection exposes the same exact-version lifecycle without
making issue resolution an Atomize capability.

## Support-module ownership

The active semantic records and projections live under
`memcommit.application.operations.atomize`. The canonical active modules are
`domain`, `workbench`, `normal_form`, `result_adapter`, and
`resolution_adapter`, together with the typed analysis/application runtimes.
Domain and saved analysis records remain independent of Store, provider
decoding remains non-mutating, normal-form planning publishes no partial
state, and both presentation adapters remain read-only projections.

The `grounding` package and the executable `grounding_application`,
`grounding_provider`, `grounding_runtime`, and `grounding_meld_adapter`
modules are removed together with their Store, history, restoration,
console, Python, and agent adapters. Structural legacy facades that are
unrelated to Grounding continue to preserve their existing import identity.

The responsibility revision does not change analysis or workbench schema
versions; semantic planning bounds; complete-frame exposure; strict provider
decoding; CAS and checkpoint behavior; or Dedun-backed normal-form validation.
Legacy response bytes still participate only in workbench stale-state safety;
Grounding artifacts have no active decoder or restoration contract.

## Current execution junction

Atomize separates semantic records, strict provider decoding, mutable
workbench state, application/runtime use cases, and presentation. The stable
Python surface exports the full structural lifecycle through those same use
cases:

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
exact opaque session revision
        |
        +-- Output plan edit --> provider-free CAS replacement
        |
        +-- in place --> recover/create one Source checkpoint
        |                + CAS-save terminal receipt
        |                + compensate an uncommitted exact checkpoint
        |
        `-- save-as  --> publish one require-new Atomize creation checkpoint
                        + Source-owned receipt + current switch
        |
        v
typed Apply result or retained save-as state
        |
        v
render compact command receipt (effect counts + every unresolved issue on one
logical line + receipt/checkpoint identities + `mem review atomize` handoff)
```

`memcommit.application.operations.atomize.application` owns provider-free Output
planning and both application lifecycles, and imports no terminal adapter or
Store. `memcommit.application.operations.atomize.runtime` owns the Store session
repository, strict graph preflight, checkpoint reconstruction,
materialization, and compensation. The
Context/checkpoint and workbench receipt remain separate
atomic files, but the application result treats them as one synchronous
outcome: it re-reads late success, compensates an uncommitted new checkpoint,
and recovers an exact previously interrupted checkpoint without replaying the
transformation.

`memcommit.application.operations.atomize.analysis_application` owns the open
request/result, origin contract, and result validation without importing
Store, commands, Typer, or prompt-toolkit.
`memcommit.application.operations.atomize.analysis_runtime` owns saved-pair lookup,
hidden-prewarm lookup, lazy provider connection, Context freshness recheck,
pair publication, and the synchronous restoration path. The legacy
`atomize_workflow` module remains a compatibility facade over structural
analysis only.

## Operation-owned decisions to preserve

- Atomize applies exactly one immutable semantic analysis identity at most
  once. Undo, later edits, or loss of a derived Output do not rearm it.
- `COMPOSITE` replaces one source occurrence in place with fresh child UIDs.
  `ATOMIC`, `UNCERTAIN`, and `NON_PROPOSITIONAL` preserve source UID and text.
- Ambiguity, Atomize Uncertainty, and Conflict findings never become implicit
  answers or semantic input. Applying the exact proposal records `AS_IS` and
  the complete unresolved issue audit in the checkpoint.
- Previously saved workbench responses remain part of the opaque record and
  stale-state digest, but Atomize neither edits nor incorporates them.
- An all-preserved analysis is a deliberate recorded completion: it creates an
  Atomize checkpoint and terminal receipt even though Context Memory bytes do
  not change. This differs from Update's zero-operation receipt-only no-op and
  from Sever SELF-SAVE's reviewed in-place completion and Sever OTHER-SAVE's
  all-KEEP require-new Result.
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
- Ordinary `mem atomize`, with or without an explicit `--context`, freezes that
  exact ordinary Context, opens the complete whole-Context analysis scope, and
  immediately requests in-place Apply. It
  does not grant a launcher, workbench, or saved Output plan authority to
  redirect that ordinary route. `--sessions`, `--output`, and `--memory`
  retain the advanced structural workflow; there is no Grounding action.
- An applied terminal workbench plus its recognized checkpoint is sufficient
  to reopen the complete analysis in read-only Review after the live Context
  digest changed. It is not sufficient to edit a response or reapply the
  semantic result.

## APPLY-01 case matrix

| Case | Current effect | Evidence state | Extraction requirement |
| --- | --- | --- | --- |
| Preview or workbench open | Analysis/workbench artifacts only; no Context checkpoint | existing preview, workbench, and Study-prewarm tests | typed analysis result must remain non-applying |
| Ordinary exact-Context command | compatible complete analysis is created/reused and immediately applied in place; no launcher or workbench is opened | bare and explicit-Context execution tests | freeze exact name, complete scope, and in-place Output before ordinary Apply |
| Compact direct receipt | split/child/keep counts and every unresolved issue on one logical line accompany up to three exact source-to-child effect groups; additional splits hand off explicitly to exact post-application Review; a first-use prepared hit also states `ANALYSIS · EXACT PREWARM · PROVIDER NOT CALLED` | compact receipt, prepared auto-Apply, and applied Review tests | changed Memory content is bounded proof rather than a second report; unresolved evidence is complete, while omitted split proofs are named explicitly |
| Applied Review reopen | complete analysis remains read-only and provider-free despite the post-split Context digest; each item title pairs source UID with its content preview, while applied children render as `APPLIED CHILD MEMORIES` with explicit `MEMORY n` rows | direct receipt/review and adapter tests | accept only exact terminal receipt/checkpoint evidence; reject response edits; retain source-span evidence without repeating it in the default snapshot |
| Close/cancel before final action | Saved review may remain; no Context effect | shared Resolution CLOSE and workbench persistence tests | application port must never be called |
| Local current analysis, one or more splits | one in-place Context checkpoint, complete SPLIT/KEEP/PRESERVE trace | `test_saved_atomize_analysis_applies_once_with_recorded_lineage` | consume exact analysis and workbench revision |
| Every item preserved | one no-change Atomize checkpoint and terminal receipt | `test_all_atomic_apply_records_a_deliberate_no_change_checkpoint` | preserve this explicit Atomize no-op variant |
| Unresolved findings | exact current proposal applies; checkpoint records `AS_IS` and the complete unresolved issue set | unresolved receipt and Apply-audit tests | no response or missing response may alter the structural proposal |
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
| Save-as structural Apply | new Context, one Atomize creation checkpoint, copied analysis, current-pointer CAS, Source terminal receipt | one Undo/Redo removes/restores the complete created Context and Source receipt | verified as one command unit for new histories |
| Save-as failure after publication | exact inspectable new Context in its last durable phase; Source unchanged | exact retry completes missing receipt/selection without a second checkpoint | verified retained-publication recovery |
| Structural Apply receipt failure | synchronous pre-commit failure exposes no Context effect; a prior exact checkpoint is recoverable without replay | checkpoint/receipt pair remains one application outcome | verified for local in-place Apply |
| Legacy Grounding checkpoint | no new route writes one; generic before/after snapshots remain readable | Context snapshot restoration only; no companion session synchronization | keep artifact bytes inert without reviving Grounding ownership |

## Hidden prewarm and visible-session boundary

The Study Atomize prewarm is a hidden declared artifact, not a pre-created user
session. Initialization validates and installs only its hidden entry receipt.
The first explicit matching Atomize invocation materializes the prepared
analysis through the ordinary production slot and creates a blank run-local
workbench. A mismatch, stale Source, lower/incomparable cached provider
quality, or failed
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

- `memcommit.application.operations.atomize.application`: implemented typed requests/results,
  lifecycle ordering, idempotence, audit projection, and port protocols; no
  Typer, prompt-toolkit, Store paths, or Study fixture imports.
- `memcommit.application.operations.atomize.runtime`: local Context capture, strict graph preflight,
  session repository, Context materialization, compensation, and
  interrupted-Apply recovery.
- `memcommit.application.operations.atomize.analysis_application`: implemented typed
  analysis-open request/result, exact origin validation, and
  terminal-independent port.
- `memcommit.application.operations.atomize.analysis_runtime`: saved-pair and
  hidden-prewarm lookup, lazy provider analysis, freshness recheck, and pair
  publication/restoration.
- `memcommit.adapters.console.commands.atomize.command`: CLI/TUI composition, progress and receipts,
  mapping final workbench actions to the typed in-place or Save As use case;
  the command retains presentation policy but not either materialization
  lifecycle.
- existing `memcommit.atomize`, `atomize_workbench`, and grounding modules:
  semantic/domain records and their operation-specific validation; schemas are
  not merged merely because lifecycle mechanics become common.

The flat `memcommit.atomize_application` and `memcommit.atomize_runtime`
paths remain identity-preserving compatibility aliases. Importing either old
or canonical path first therefore reaches the same module globals, preserving
existing monkeypatches and serialized globals while production consumers use
the operation package directly. This relocation changes no session schema,
provider call, whole-frame constraint, reconciliation, authority, CAS,
checkpoint, compensation, or receipt behavior.

The flat `memcommit.atomize_analysis_application` and
`memcommit.atomize_analysis_runtime` paths are also identity-preserving
compatibility aliases for their sibling canonical modules under
`memcommit.application.operations.atomize`. The Analysis relocation retains the complete
current runtime, including displaced-session archival and rollback, without
changing provider/cache selection, refresh meaning, pair publication, session
schema, semantic budgets, or reconciliation.

The package groups related ownership without merging slice contracts. Primary
structural application remains in `application` / `runtime`; analysis open,
reuse, refresh, provider/cache, and pair-publication policy remains in
`analysis_application` / `analysis_runtime`. Grounding executable siblings,
schema package, and legacy load/history/restoration handlers no longer exist.
No shared package location creates resolution or mutation authority.

The opaque session revision binds the immutable analysis record and complete
workbench record, including legacy response bytes, Output plan, and any
application receipt. Legacy bytes participate only in stale-state safety; they
are not an editable capability. Every ordinary analysis/workbench writer
shares one Context-scoped session lock, and the repository rechecks the token
before terminal publication.

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
6. **Done:** expose exact Output planning, in-place Apply, and require-new Save
   As through stable Python and agent contracts; retire response, reanalysis,
   compound, and Grounding routes.
7. **Done:** make new save-as histories one Atomize creation unit; leave
   pre-release legacy `init + atomize` histories uninterpreted.

## Current verification evidence

Focused public/application/agent tests cover provider creation, provider-free
saved resume, exact hidden-prewarm materialization, focused Memory open,
read-only issue projection, Output plan validation, in-place and Save As
receipts, exact recovery, lineage, stale rejection, absent response/Grounding
routes, and adapter dependency direction.
The complete regression and installed-wheel gates are rerun with every change;
the current recorded commands live in the public and agent rationale notes.

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
- no change to `APPLY`, `APPLY AS IS`, or ownership-aware presentation policy;
- no deletion or cleanup of a published save-as destination;
- no migration or deletion of inert legacy Grounding artifact files;
- no conversion of pair-shaped conflicts into unary provider guidance; and
- no expansion from local ordinary Contexts to Grant-authorized mutation.

## Historical 2026-08-20 execution-receipt migration (superseded)

Atomize execution ends with effect counts, a bounded proof of up to three exact
source-to-child split groups, analysis/session receipt, checkpoint,
post-application `mem review atomize`, and recovery. The bound keeps large
receipts scannable while an explicit omitted-split line prevents compactness
from being mistaken for complete effect evidence. Required responses remain
owned by the Atomize invocation; Review accepts only an applied analysis and is
read-only. This supersedes earlier wording that treated Review as an execution
resume surface. The full analysis is retained, not discarded.

# Resolve application-boundary matrix

Last reviewed: 2026-08-31.

## Operation shape

```text
freeze one complete direct Context and exact authority
        |
        v
find newest exact saved Audit ── missing/stale ──> run + save complete Audit
        |                                      (duplicate, ambiguity, conflict,
        |                                       whole-Context Fit,
        |                                       optional Rule conformance)
        v
derive one non-mutating direction for every actionable Audit item
        |
        v
ACCEPT / INTENT / LEAVE UNRESOLVED for every item
        |
        v
one process-local Source containing all accepted direction and intent input
        |
        v
ordinary Update once over the complete Target -> exact UpdatePlan
        |
        v
detached complete post-image -> complete Audit with the same Rule frame
        |
        +----------------------------------+
        |                                  |
no unpermitted Audit issue       new/unaccepted Audit issue
        |                                  |
Resolve atomic publication              no write
```

## Ownership matrix

| Concern | Canonical owner | Boundary |
| --- | --- | --- |
| Resolve request and frozen frame | `application.operations.resolve.application` | One exact direct Context, complete direct Memory frame, exact actionable identities and effect capabilities |
| Issue discovery and persistence | `application.operations.audit` | Audit runs three independent finder checks, one whole-Context Fit judgment for a multi-Memory Source, and optional Conformance; it retains exact provenance and stores one immutable completed snapshot |
| Direction synthesis | `application.operations.resolve.semantic` | Projects every actionable Audit item unchanged and asks for exactly one conservative direction; it cannot rediscover, merge, omit, or mutate findings |
| Human decisions | `application.operations.resolve.decisions` | Exactly one typed `CONFIRM`, `INTENT`, or `FORCE` decision per frozen Audit item |
| Process-local Source projection | `application.operations.resolve.decisions` | Every confirmed direction and supplied intent enters one Source frame; FORCE is control state and never evidence |
| Exact mutation planning | `application.operations.update.model.plan_update` | One ordinary Update turn over the complete frozen Target |
| Detached plan application | `application.operations.update.application.apply_update` | Exact operations validated without persistence |
| Complete post-image composition | `application.operations.update.application.materialize_update_post_image` | Rejoins owner post-images for inspection without mutating the frozen Target |
| Post-image verification | `application.operations.audit.application.run_quality_audit` | Repeats the complete Audit; if the source Audit had Conformance, it reuses that exact frozen Rules frame |
| Resolve Apply and checkpoint | `resolve.runtime.MemoryStoreResolvePort` | Authority, freshness, pre-images, inbound references, CAS, one checkpoint |
| Interactive decisions | Resolve console `workbench/` over the shared compact shell | Resolve supplies its three-choice meaning and choice-bound editor; the shell owns only rendering and keys |
| Impact | Resolve console `impact.py` | Shows Audit directions and the explicitly absent Update plan |
| Python and agent projections | `adapters.python_api` and `adapters.agent` | Typed decisions cross the adapter; application contracts remain canonical |

## Invariant matrix

| Invariant | Host enforcement | Failure behavior |
| --- | --- | --- |
| Resolve enters through Audit | `get_or_run_quality_audit` matches Context UID plus exact direct-Memory digest | An exact saved Audit is reused; a missing or stale Audit is rerun completely and saved before directions are shown |
| Audit judgments stay Audit-owned | Resolve direction payload carries immutable item identities, classifications, reasons, questions, and members | The direction provider cannot add, remove, merge, split, or reclassify an Audit item |
| Fit remains set-level | Audit retains complete ordered coverage and the material subset; Resolve projects only `MAY` or `NO` | One Fit judgment becomes exactly one `FIT` item, never pairwise or per-Memory findings; `YES` produces no item |
| No automatic resolution | Direction output is a proposal and has no mutation schema or authority | No human decision means no Update planning or Apply |
| One decision per item | `finalize_resolve_decisions` compares exact item identities | Missing, duplicate, or unknown decision fails before Update provider construction |
| Decisions bind to one snapshot and revision | Every issue contains the Audit snapshot digest; the decision set contains the frozen Resolve revision | A changed Audit, Context, or capability frame fails closed |
| Complete Target planning | Resolve passes all accepted input together and the entire loaded Target to `plan_update` once | No per-item partial plan is published |
| Update solely owns mutations | Resolve consumes `UpdateSession.plan`; it has no candidate/effect generator | Invalid Update operations fail at Update or Resolve publication boundaries |
| FORCE is not evidence | FORCE is omitted from the process-local Source Context | A force-only turn produces an empty UpdatePlan and may write only the reviewed unresolved checkpoint |
| Full detached verification | Exact plan is applied, recomposed, then audited as one complete post-image | Any new or non-permitted duplicate, ambiguity, conflict, Fit, or Conformance issue blocks Apply |
| Exact FORCE exception | Only the same frozen Audit key may remain | A different relation, Memory member, Rule judgment, or issue kind is new and blocking |
| Incidental repair is allowed | The verifier judges the actual complete post-image | A forced item no longer present is omitted from unresolved receipt state |
| Sparse atomic publication | Owner, capability, pre-image, digest, and inbound-reference checks run under the mutation boundary | Failure publishes no partial Update effect or Resolve checkpoint |
| Exact audit evidence | Checkpoint stores plan digest, operations, finalized inputs, and unresolved issue identities | A receipt is produced only after checkpoint creation |

## Console focus topology

For each Audit item the vertical decision sequence is exactly:

```text
1 ACCEPT THIS DIRECTION <-> 2 ADJUST WITH YOUR INTENT <-> 3 LEAVE UNRESOLVED
```

The visible `YOUR INTENT` field is not a fourth row. Enter on choice 2 opens
its editor. Enter or Escape freezes the draft back onto choice 2; Up and Down
freeze it and move directly to choice 1 or choice 3. Selecting choice 1 later
retains the process-local draft but excludes it from finalized Update input.
A blank choice-2 draft never counts as ready. Previous/next item controls stay
immediately above `FINALIZE DECISIONS` and are ordinary selectable actions.

The choice-bound behavior is an explicit Resolve option on the shared compact
mechanics. Existing Meld and other callers retain their independent optional
note field until their own application contracts adopt Resolve semantics.

## Adapter flow matrix

| Surface | Analyze result | Required Apply input | Durable result |
| --- | --- | --- | --- |
| Console | Compact decisions for every actionable Audit item | Finalized decision set from the same invocation | Update effect counts, post-image Audit issue count, checkpoint, unresolved count |
| Non-interactive console | Plain Audit directions | Unsupported; reopen interactively | The completed Audit may already have been saved; no Resolve checkpoint |
| Impact | Audit directions plus `UPDATE PLAN · NOT BUILT` | None | The completed Audit may already have been saved; no Resolve checkpoint |
| Python | Typed `ResolveAnalysisResult` with Audit-bound issues | Typed decision sequence and expected revision | Typed plan/checkpoint receipt |
| Agent | Revision-keyed process-local analysis | Complete JSON decisions and expected revision | Structured receipt; cache consumed after success |
| Quality-finding handoff | Finder source precondition becomes a Resolve request | Same complete-Audit decisions as ordinary Resolve | Same Resolve checkpoint |

## Regression boundary

- Audit tests prove exact saved-snapshot reuse and complete rerun after a
  direct-Memory change.
- Direction decoder tests require exact coverage of Duplicate, Ambiguity,
  Conflict, one set-level Fit item when applicable, and optional Conformance
  items, and reject mutation-shaped output.
- Decision tests cover exact completeness, one combined process-local Source,
  FORCE exclusion, and retained checkpoint evidence.
- Update integration tests prove one whole-Target planning call and detached
  post-image materialization.
- Verification tests cover an exact remaining forced key and a blocking new
  Audit key.
- TUI tests cover ACCEPT, inline INTENT, LEAVE UNRESOLVED, a non-focusable
  input row, blank-intent readiness, previous/next actions, and finalization.
- Color-capable 180x52 PTY captures record entry, every decision/input
  transition, Update, post-image Audit, receipts, and read-only verification.
  The focused Fit branch is recorded under
  `agent-records/docs/screenshots/audit-fit-resolve-20260831/`.

## Current limitations

- The runtime boundary is one direct Context owner; it does not publish an
  Update plan that targets an embedded or second Context owner.
- A clean post-image Audit is not a truth proof. It is the exact bounded gate
  for this Resolve Apply.
- Fit is not a separate hard gate. A `MAY` or `NO` follows the same exact-item
  decision path, including an explicit FORCE exception for that same key.
- Conformance participates only when the reused source Audit contains it or
  the invocation supplies an explicit Rules Context.
- Decision drafts are not a persisted session schema. Only a completed Audit
  and finalized inputs in a successful Resolve checkpoint are durable.
- Other semantic operations do not inherit the choice-bound Resolve behavior
  until they explicitly adopt the same decision and Update contracts.

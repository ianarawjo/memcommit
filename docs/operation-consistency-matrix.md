# Operation consistency matrix

## Status

Initial repository-wide contract map, reviewed 2026-08-15.

This document is a work ledger, not a claim that all listed operations already
conform. It starts from the 57 visible operations in
`memcommit.help_catalog.catalog`. A contract becomes `VERIFIED` only after its
applicable operations, intentional exceptions, tests, and interface evidence
have been reviewed together.

The matrix is organized by shared contract rather than by operation. This lets
one bounded consistency rule be migrated across every applicable operation
without turning an operation's distinct meaning into one universal workflow.

## Reading the matrix

### Disposition

- `SHARED CONTRACT`: the invariant, lifecycle, and failure boundary must be the
  same for every applicable operation.
- `SHARED MECHANICS`: interaction or scheduling mechanics are common, while the
  operation retains its own semantic values and validation.
- `OPERATION OWNED`: the behavior must remain independently defined.
- `INTENTIONAL VARIANT`: a reviewed difference from a shared default.
- `UNKNOWN`: current behavior has not yet been characterized well enough to
  classify.

### Evidence state

- `CATALOGUED`: candidate scope is complete enough to begin investigation, but
  conformance is not claimed.
- `CHARACTERIZED`: current behavior and exceptions are protected by tests or an
  operation trace.
- `MIGRATING`: applicable callers are moving to the chosen owner.
- `VERIFIED`: every applicable caller uses the contract or has a tested,
  documented intentional variant.
- `DEFERRED`: work is deliberately postponed with a named resumption condition.

`N/A` is recorded at the operation level only after review. Absence from a
candidate list does not yet prove that a contract is inapplicable.

## Shared-contract ledger

| ID | Contract | Disposition | Candidate operations | Shared invariant | Operation-owned variation | Current evidence | State | Next gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `APP-01` | Interface-independent application entry | `SHARED CONTRACT` | All 57 operations | CLI, TUI, public Python, and agent projections call one typed use case; application code imports no terminal adapter | Which public adapters are exposed and how errors are presented | Verified vertical slices exist for Add and Query; Summarize, Context Init, Embed, Find, Fit, Sever, and Merge provide additional internal evidence | `CHARACTERIZED` | Generate the callable/import catalog, then remove CLI-to-TUI and interface-to-command policy dependencies one operation at a time |
| `APP-02` | Context locator, readable catalog, targeting, and reach | `SHARED CONTRACT` + `SHARED MECHANICS` | add, atomize, audit, branch, checkout, checkpoint, check-conformance, chunk, clear, compare, contexts, delete, diff, distill, edit, embed, find, find-ambiguities, find-conflicts, find-duplicates, forget, impact, import, list, lock, log, meld, merge, query, rationale, reference, revert, sever, share, show, status, summarize, switch, trace, translate, unlock, update | Capture current once; canonicalize existing locators; keep readable names, Grant metadata, lexical descendants, embedded traversal, and selected exact sets distinct | New-name operations, query-only routes, per-role authority, one-vs-many selection, and exact-vs-descendant defaults | Context locator and Context targeting rationales; shared selection and readable-catalog components | `CHARACTERIZED` | Produce an operation-by-operation operand/reach audit and close parallel picker/resolver paths |
| `APP-03` | Authority, disclosure freeze, and freshness revalidation | `SHARED CONTRACT` | Every operation that reads, transfers, derives from, or mutates Context/Memory/Profile material; initially the `APP-02` set plus init, init-study, profile, provider, rename, ground, undo, and redo where their resources require it | Required authority is checked before disclosure or mutation; frozen identities are revalidated at Apply; interfaces cannot infer permission from visibility | Required permissions (`READ`, `CREATE`, `UPDATE`, `COMBINE`, `EXPORT`, `SAVE_*`, and others), local-vs-granted targets, and lock set | Strong slice evidence in Add, Query, Find, Sever, Embed, Context Init, and Merge; repository-wide coverage remains unknown | `CHARACTERIZED` | Build a permission/effect table per operation and test every pre-provider and pre-Apply failure boundary |
| `SEM-01` | Provider trust and semantic-execution boundary | `SHARED CONTRACT` + `OPERATION OWNED` strategy | atomize, audit, check-conformance, compare, distill, eval, find, find-ambiguities, find-conflicts, find-duplicates, fit, forget, ground, impact, meld, query, rationale, sever, summarize, translate, update | Freeze and authorize input before provider construction; one failed staged run publishes no partial result; provider output crosses a strict decoder | Execution strategy, whole-frame requirement, batching, reconciliation, schema, and retained dialogue | Shared semantic-execution plan plus verified Query, Summarize, Sever, Find, and Fit slices | `CHARACTERIZED` | Inventory every provider factory/`complete()` route and link it to an explicit strategy and pre-disclosure test |
| `CACHE-01` | Hidden prepared-analysis lookup and projection | `SHARED CONTRACT` with operation-owned proof | atomize, compare, meld directional, meld resolution, sever, summarize, update | Authority and complete frozen evidence precede lookup; a valid hit avoids provider construction; exact/equivalent/projected reuse must preserve the requested operation contract; hidden installations do not become visible sessions before invocation | Cache key, graph/scope equivalence proof, safe subset projection, result decoder, and user-visible origin | Study prewarm registry covers the seven named artifact kinds; Summarize and Sever have extracted application ports; operation parity is incomplete | `CHARACTERIZED` | Audit exact, ancestor-equivalent, descendant-subset, relative-path, granted, empty, and stale cases for each applicable operation |
| `SESSION-01` | Saved analysis, opaque revision, and CAS lifecycle | `SHARED CONTRACT` + `OPERATION OWNED` schema | atomize, audit, compare, fit, forget, ground, impact, meld, review, sever, translate, update; investigate find and quality-report sessions separately | Interfaces receive opaque snapshots/tokens; create/open/revise/apply revalidate one exact revision; stale or repeated actions cannot publish a second effect | Persisted schema, which decisions are durable, session visibility, resume behavior, and whether analysis is saved at all; Fit is an immutable create-only derived receipt, not a revisable Apply session | Fit receipt publication and stale reopening are characterized; Sever is verified; Resolution-family operations retain several legacy repositories and shells | `CHARACTERIZED` | Inventory every remaining session repository and digest calculation, then choose one opaque lifecycle contract without merging schemas |
| `APPLY-01` | Review, no-op, final approval, and materialization | `SHARED CONTRACT` + `OPERATION OWNED` decision model | atomize, branch, checkout -b, chunk, clear, delete, distill, edit, embed, find materialization, forget, ground, import, init, lock, meld, merge, profile mutations, reference, rename, revert, sever, share, translate materialization, undo, unlock, update | Review does not mutate; final action is explicit; no-op is represented deliberately; Apply consumes the exact reviewed/frozen state and returns a complete result | Whether exact argv is shown, required vs optional items, bulk choice, custom content, idempotence, and destination creation/update semantics | The exact-review value identity is unified; approval/no-op policies and the legacy/new Resolution shells remain under characterization | `CATALOGUED` | Characterize approval/no-op behavior for every candidate and migrate each applicable family without merging its decision model |
| `EFFECT-01` | Receipt, checkpoint, operation-unit Undo/Redo, and rollback | `SHARED CONTRACT` with explicit applicability | add, atomize, branch, checkout -b, chunk, clear, delete, distill Apply, edit, embed, forget Apply, import, init, meld Apply, merge, reference, revert, sever Apply, translate materialization, update Apply; plus profile/config/protection mutations requiring a documented non-Undo boundary | A success receipt covers the complete command effect; multi-Context effects form one unit; failed publication exposes no partial success; Undo support or exclusion is explicit | Checkpoint payload, crash-recovery mechanism, irreversible external effect, and whether an operation is intentionally outside Undo | Semantic Apply Undo rationale and several vertical slices; repository-wide mutation inventory is incomplete | `CATALOGUED` | Map every durable write and checkpoint producer, then test success, no-op, mid-Apply failure, Undo, and Redo per supported operation |
| `TUI-01` | Endpoint setup and frozen operation shape | `SHARED MECHANICS` | atomize, audit, compare, embed, meld, merge, sever, update; investigate branch, check-conformance, distill, find, forget, query, and translate where they select multiple roles or modes | One visible role-based setup; selection returns process-local typed values only; setup performs no provider call or durable mutation; final operation validation remains authoritative | Role symmetry/direction, selectable catalog, independent per-role range/memory focus, fixed endpoint, fresh result name, and modes | The new `interfaces.tui.components.endpoint_setup` owner is used by Merge and Audit and freezes all four A/B exact-or-descendant combinations plus lazy role-local direct-Memory focus; Context or descendant changes clear stale UIDs, while the legacy path remains authoritative for new-Context and mode-dependent-role capabilities | `MIGRATING` | Migrate Compare or Update with operation-owned authority and request translation, then retire only the matching legacy capabilities after parity evidence |
| `TUI-02` | Selection, focus topology, back navigation, and writable-input protection | `SHARED MECHANICS` | Every interactive operation: atomize, audit, branch, checkout, compare, contexts, delete, diff, embed, eval, find, fit, forget, ground, help, history/log, impact, import, init, meld, merge, profile, provider, query, rationale, reference, revert, review, sever, share, summarize, switch, translate, update, plus interactive variants discovered by the callable catalog | Shared focus controller reports movement/boundary/consumption; Escape has an operation-owned exit path; Backspace is not stolen from writable input; visible frame order determines traversal | Surface topology, defaults, labels, operation actions, and editor validation | Shared core, frame, focus, scroll, input, choice, targeting, and selection owners are now inventoried below; many command-hosted screens still compose them beside newer operation adapters | `CHARACTERIZED` | Complete the prompt-toolkit application/import inventory, then migrate by component family with parity tests rather than by visual resemblance |
| `TUI-03` | Resolution workbench | `SHARED MECHANICS` + `OPERATION OWNED` semantic projection | atomize, audit findings where answerable, forget, meld, merge, review, sever, update; inspect impact and quality findings as read-only/adaptive variants | Viewer, conditional Responses, Items, optional Save Location, and To Do share topology; required items gate Apply; response and final action remain separate; workbench never bypasses application validation | Detail document, issue/conflict types, choices, custom-response permission, whole-set strategy, Apply effect, and saved schema | A 4,757-line legacy shell and a smaller new interface workbench coexist; adapters target both generations | `MIGRATING` | Characterize feature parity, select one owner, migrate one operation family at a time, and prohibit new operation-local Resolution shells |
| `TUI-04` | Exact command review | `SHARED CONTRACT` + `SHARED MECHANICS` | embed, ground, import, merge, Profile rename/removal; Find SHOW is a receipt-only read action | One interface-neutral immutable argv/effects value and one escaped renderer; a consequential final review uses focused `Enter`, cancellation publishes nothing, and writable editing cannot coexist with approval | Ground and Find dispatch allowlisted argv; Import, Profile, Embed, and Merge apply an adjacent frozen typed plan/action; `A` remains a legacy alias where already published | [Consumer-boundary rationale](exact-command-review-consumer-boundary-design-rationale.md); type identity, rendering, every execution binding, cancellation, Embed single-use application, Merge plan/conflict application, and the read-only Find SHOW receipt are verified | `VERIFIED` | Keep the row closed under every new consumer; audit application policy separately under `APPLY-01` |
| `TUI-05` | Semantic/read-only Viewer, clipboard, and result verification | `SHARED MECHANICS` | compare, diff, find, fit, help detail, impact, query, rationale, review reports, show, summarize, trace; Resolution operations reuse only the compatible Viewer layer | Neutral report chrome; Memory objects use Memory styling; focused section/cross-section copy is deterministic; read-only exit never mutates | Typed document/detail model, citations, Fit judgment/freshness vocabulary, diff semantics, source-member grouping, and copy scope exposed by the operation | Fit's plain/TUI parity, current/stale projection, and focused/whole copy are verified in the shared Viewer; several other command-hosted viewers retain local rendering | `MIGRATING` | Use the Fit slice as mechanics evidence, then inventory the remaining compatible result surfaces without copying its semantic document |
| `HELP-01` | Stable operation discovery and interface-specific syntax | `SHARED CONTRACT` + `SHARED MECHANICS` | All 57 operations | One canonical summary/flow/execution/effect/range record; CLI, TUI, Python, and agent projections do not invent semantic meaning | CLI flags/forms, runtime authority/cache receipts, detailed algorithms, and operation rationale | The 57-entry Help catalog is verified; Help's remaining TUI/controller and agent projection are not fully relocated | `CHARACTERIZED` | Keep catalog coverage closed while moving Help presentation behind interface owners and adding the agent projection |
| `CONFIG-01` | Typed runtime configuration and provider construction | `SHARED CONTRACT` | Every provider-using operation in `SEM-01`; config, provider, eval, and ground also administer or inspect related state | Validate one effective request snapshot; secrets and endpoint policy stay in infrastructure; operations do not hardcode behavioral limits | Operation-specific budgets, schemas, model requirements, and supported provider capabilities | Typed accessors exist but duplicated defaults and operation-local overrides remain | `CATALOGUED` | Freeze key ownership/precedence/bounds and enumerate every construction site before relocating it |

## Shared TUI component ledger

The application matrices describe complete operation lifecycles.  This second
view records which terminal interaction mechanics are genuinely shared across
those operations.  A package is not considered a verified common component
merely because it lives under `interfaces/tui/components`: it must have a
stable behavior contract, more than one applicable consumer or an explicit
provisional status, parity evidence, and no unrecorded parallel owner.

| ID | Component family | Chosen owner | Confirmed consumers | Shared invariant | Parallel or operation-owned boundary | State | Next gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `TUI-C01` | Core terminal mechanics | `memcommit.interfaces.tui.core` | New Add, Embed, Fit, Merge, Query, and Summarize surfaces; command-hosted screens also import selected core helpers | Theme semantics, safe text layout, buffer/activity helpers, and layered back-key grammar do not own operation meaning | Screen topology, labels, validation, and actions remain operation-owned; legacy `commands.tui_primitives` still combines several mechanics | `MIGRATING` | Inventory every remaining primitive and reduce the command module to compatibility imports or named operation-only behavior |
| `TUI-C02` | Frame and focus surfaces | `interfaces.tui.components.frame` and `.focus` | Add, Endpoint Setup, Embed, Merge, Query, semantic/read-only viewers, shared workbenches, and numerous legacy command screens | Frames compose top-to-bottom; focus movement reports moved/boundary/consumed; visible order determines traversal | Each screen defines its own visible surfaces and activation meaning | `CHARACTERIZED` | Add family-level traversal and Escape/Backspace parity tests, then close duplicate focus-index implementations |
| `TUI-C03` | Scrolling, choice, input, background turn, and clipboard mechanics | `interfaces.tui.components.scrollable_pane`, `.horizontal_choice`, `.in_frame_input`, `.multiline_input`, `.background_turn`, and `.plain_text_clipboard` | Add and Query are the broadest new consumers; Fit uses shared clipboard and the Ground Fit turn uses shared background lifecycle; Merge and Resolution screens use narrower pieces | Cursor/viewport mechanics, writable-input protection, one background-turn lifecycle, and plain-text clipboard injection remain presentation-only | Choice content, validators, cancellation policy, provider lifecycle, and copied semantic scope stay with the operation adapter | `MIGRATING` | Classify every legacy helper against these owners and prove remaining caller parity before treating a provisional helper as universal |
| `TUI-C04` | Context targeting and generic selection | `memcommit.context_targeting.tui` and `memcommit.selection.tui` | Add, Context Init, Embed, Query, Summarize, Endpoint Setup, and many command-hosted operations | Context tree, exact/descendant reach, checked selection, and common selection rendering preserve their typed state contracts | Readable catalogs, authority, role availability, defaults, Memory materialization, and receipts remain operation-owned | `MIGRATING` | Remove operation-local picker/resolver mechanics after operand, Grant, and empty-selection parity is recorded |
| `TUI-C05` | Endpoint Setup | `interfaces.tui.components.endpoint_setup` | Merge and Audit; the Memory-focus contract is component-tested before its first directional migration | Modes and named roles produce one process-local typed draft; fixed roles, independent per-role descendant reach, and exact direct-Memory focus are visible; Context or descendant changes clear stale UIDs; cancellation performs no provider call or durable write | Authority, caller-owned projection loading, new Context naming, plan preparation, and Apply remain outside the component | `MIGRATING` | Migrate Compare or Update through the typed Context/range/Memory value and verify its existing authority, cache, session, and plain-interface parity |
| `TUI-C06` | Exact command review | `interfaces.tui.components.exact_command_review` | Embed, Merge, Ground/Profile command screens, and the new Resolution workbench | One immutable argv/effects identity and one escaped projection back focused Enter approval; cancellation publishes nothing | Allowlisted dispatch and adjacent frozen plan/application policy remain operation-owned; Find SHOW is explicitly receipt-only | `VERIFIED` | Require the same consumer audit before admitting another operation |
| `TUI-C07` | Semantic and read-only viewers | `interfaces.tui.viewers.semantic` and `.read_only` | Fit, Summarize, and Merge use the new owners; Compare, Rationale, Trace, and Share retain compatible command-hosted consumers | Neutral report chrome, Memory styling, focus anchoring, scrolling, and deterministic focused/whole-document copy are shared mechanics | Typed documents, citations, Fit judgment/freshness vocabulary, relation grouping, diff meaning, and copyable semantic scope remain operation projections | `MIGRATING` | Verify the Fit vertical slice, then build the remaining operation-by-operation viewer/copy matrix |
| `TUI-C08` | Context-summary and Resolution workbenches | `interfaces.tui.workbenches.context_summary` and `.resolution` | Summarize and Merge are new consumers; legacy Resolution-family operations still use the command-hosted shell | A workbench composes shared components into a stable visible-frame and review topology without owning domain decisions | Required/optional meaning, responses, conflict schema, no-op, save location, Apply, and CAS remain operation-owned | `MIGRATING` | Characterize legacy/new feature parity and migrate one Resolution family without merging its persisted schema |
| `TUI-C09` | Direct item placement | `interfaces.tui.components.direct_item_placement` | Embed only in the new operation packages | Exact item selection and placement remain typed and read-only until operation submission | Its present single-operation use does not yet prove a repository-wide component contract | `PROVISIONAL` | Reuse only when a second operation demonstrates the same invariant; otherwise keep it operation-adjacent |
| `TUI-A01` | Per-operation TUI adapters | `interfaces.tui.operations.<operation>` | Add, Audit, Context Init, Embed, Fit, Merge, Query, and Summarize | Each adapter translates typed application values to shared mechanics and must not become a second application service | Compare, Update, Meld, Sever, Atomize, and many smaller screens remain under `commands/` until migrated with parity evidence | `MIGRATING` | Link each migrated adapter to its application matrix and record every remaining command-hosted operation or tested `N/A` |

## Operation-family coverage

Every visible operation appears exactly once below. Families are investigation
units, not proposed universal implementations.

| Family | Operations | Primary contracts to audit first | Important non-uniformity |
| --- | --- | --- | --- |
| Read-only Context orientation and browsing | contexts, list, pwd, show, status, switch | `APP-01`, `APP-02`, `TUI-02`, `TUI-05`, `HELP-01` | Switch mutates only the process-global current pointer; the others are reads, and `pwd` deliberately loads no Context |
| Direct deterministic Memory/Context mutation | add, chunk, clear, delete, edit, embed, reference | `APP-01`–`APP-03`, `APPLY-01`, `EFFECT-01`, `TUI-02`, `TUI-04` | Embed/reference retain identity relationships; clear/delete are destructive; Add is a batch append |
| Namespace, Profile, distribution, and protection administration | branch, checkout, config, import, init, init-study, lock, profile, provider, rename, share, shell-init, unlock | `APP-01`–`APP-03`, `APPLY-01`, `EFFECT-01`, `TUI-02`, `TUI-04`, `CONFIG-01` | New-name operands must not use the existing-Context locator contract; Share is external; shell-init is read-only output; several mutations are intentionally outside Context Undo |
| History, recovery, lineage, and explanation | checkpoint, diff, log, rationale, redo, revert, trace, undo | `APP-01`–`APP-03`, `EFFECT-01`, `TUI-02`, `TUI-05` | Rationale may infer; Undo/Redo operate on command units; Diff/Log/Trace are read-only; Revert is reviewed mutation |
| Semantic read and report operations | audit, check-conformance, compare, find, find-ambiguities, find-conflicts, find-duplicates, fit, impact, query, review, summarize | `APP-01`–`APP-03`, `SEM-01`, `SESSION-01`, `TUI-01`–`TUI-03`, `TUI-05` | Fit saves an immutable derived receipt without changing Ground; Query has ordinary, granted, and reference routes; Review stages responses but never applies; Impact may be a handoff rather than the owning operation |
| Semantic staged mutation or derived materialization | atomize, distill, forget, ground, meld, sever, translate, update | All application, semantic, cache/session/apply/effect, and TUI contracts that apply | Forget mutates Source; Sever creates a new Result; Meld reconciles semantically; Update is directional; Ground has separately approved bindings and commands; Atomize is Study-deferred |
| Deterministic staged structural reconciliation | merge | `APP-01`–`APP-03`, `SESSION-01`, `APPLY-01`, `EFFECT-01`, `TUI-01`–`TUI-05` | Merge shares review mechanics but must remain provider-free and must not acquire Meld-style custom semantic reconciliation |
| Evaluation and discovery | eval, help | `APP-01`, `SEM-01` or `HELP-01` respectively, `TUI-02`, `CONFIG-01` | Eval changes evaluation ledgers rather than Context content; Help is a stable catalog projection and never executes an operation |

## First convergence queue

The queue is ordered by risk of duplicating a safety contract during ongoing
migration, not by visual prominence. Exact command review identity and the
second Endpoint Setup consumer have crossed their earlier gates; their
remaining work is recorded in the ledger rather than repeated as unfinished
milestones.

1. **`TUI-01` First directional migration.** Migrate Compare or Update through
   the shared Context/range/Memory draft.  Preserve its authority, cache,
   session, and plain-interface contracts before retiring the matching legacy
   setup path.
2. **`TUI-03` Resolution workbench.** Freeze required/optional, Responses,
   Save Location, To Do, no-op, bulk review, clipboard, and final-review
   behavior before adding more operation adapters.
3. **`APP-01` Adapter isolation.** Remove concrete CLI-to-TUI imports through a
   console composition boundary while preserving automatic terminal routing.
4. **`CACHE-01` Prepared reuse parity.** Audit all seven Study artifact kinds
   across exact, equivalent, projected, empty, stale, relative, descendant,
   ancestor, and granted cases.
5. **`EFFECT-01` Mutation ledger.** Enumerate every durable write and establish
   which operations support command-unit Undo/Redo and which are intentional
   exclusions.

This ordering may change when an operation trace exposes a higher-risk safety
defect. Such a change should be recorded here instead of silently changing the
rollout.

## Per-contract completion gate

A ledger row may become `VERIFIED` only when:

1. every candidate operation is classified as applicable or tested `N/A`;
2. the shared invariant and every intentional variant have an owning module;
3. the application/runtime path is testable without CLI or TUI when the
   contract crosses an operation boundary;
4. plain CLI, TUI, public Python, and agent projections use the same typed
   result wherever those adapters exist;
5. authority, cache/provider, stale state, cancellation, no-op, failure,
   receipt, and Undo/Redo cases relevant to the row are tested;
6. old implementation paths are removed or reduced to behavior-free
   compatibility imports with a named retirement condition;
7. the applicable operation matrices and focused design rationale are updated;
   and
8. any materially changed interactive flow has an ordered 180x52 PTY evidence
   set and interaction log.

## Relationship to operation-specific matrices

The shared-contract ledger answers: **which operations must agree on one
cross-operation contract?**

The shared TUI component ledger answers: **which reusable terminal owner
implements the common interaction mechanics, and which operations still use a
parallel path?**

An operation-specific boundary matrix answers: **how does one operation
implement its complete lifecycle?**

All three views are required. A cross-operation row links to each applicable
operation matrix as it is characterized. A shared TUI row records the concrete
component owner and real consumers. An operation matrix links back to the
contracts and components it satisfies. None replaces executable tests or makes
an unreviewed visual similarity authoritative.

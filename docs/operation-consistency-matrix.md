# Operation consistency matrix

## Status

Initial repository-wide contract map, reviewed 2026-08-15.

This document is a work ledger, not a claim that all listed operations already
conform. It starts from the canonical visible operation set in
`memcommit.help_catalog.catalog`. A contract becomes `VERIFIED` only after its
applicable operations, intentional exceptions, tests, and interface evidence
have been reviewed together.

Operation-level route state is deliberately not owned here. Its sole authored
source is
[`operation-route-classification.json`](operation-route-classification.json),
while operation-to-document membership is maintained in
[`operation-evidence-index.json`](operation-evidence-index.json). Their
complete human-readable projection is
[`generated/operation-evidence-index.md`](generated/operation-evidence-index.md).
States in this matrix apply only to a shared contract row; they must not be
copied into an independent `CLOSED`, `MIXED`, `LEGACY`, `N/A`, or `UNREVIEWED`
judgment for an operation. New operation work updates its focused evidence and
the canonical registry, while this ledger changes only when that work changes
a shared contract's evidence or migration state.

Focused operation matrices remain separate during the current incremental
review so distinct cache, authority, provider, receipt, and Apply meanings are
not collapsed prematurely. They may be consolidated later after their roles
and naming stabilize; existing paths are intentionally not moved in this
stage. The rationale and validation contract are recorded in
[`operation-evidence-ledger-design-rationale.md`](operation-evidence-ledger-design-rationale.md).

The matrix is organized by shared contract rather than by operation. This lets
one bounded consistency rule be migrated across every applicable operation
without turning an operation's distinct meaning into one universal workflow.

## Repository verification snapshot

The 2026-08-15 integration gate was repeated from detached clean worktrees so
uncommitted terminal captures and local evaluation output could not affect the
result.

- On `f3dcdac5`, Ruff passed across `memcommit` and `tests`, and `compileall`
  completed without an error.
- `pytest -q -k 'not task2'` on that same clean checkout passed `3,692` tests,
  skipped `1`, and deselected the `202` Task 2 tests.
- The preceding full clean run on `bb7ddaaf` collected `3,882` tests: `3,806`
  passed and `1` skipped. Its `36` failures and `39` setup errors were all inside
  the Task 2 frozen-corpus family.
- That historical drift is now represented as two explicit consumed
  calibration revisions. The unreconstructable `d98dd2bb…` V1 identity remains
  archived and fails replay against current fixtures; the current
  `2e42279f…` corpus is frozen as the default V2 identity with its own complete
  slice manifests. No existing result is silently relabelled across revisions.
- The actual installed `mem` entry point, forced to import `f3dcdac5`,
  completed `mem pwd`, `mem status --short`, `mem elaborate --help`, and the
  noninteractive `mem help` inventory. No smoke command mutated durable state.

Large local provider transcripts and exploratory result corpora are not part
of this verification snapshot. Evaluation code, strict decoders, tests,
design rationale, and content-free summaries are versioned separately from
those raw artifacts.

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
| `APP-01` | Interface-independent application entry | `SHARED CONTRACT` | All 60 operations | CLI, TUI, public Python, and agent projections call one typed use case; application code imports no terminal adapter | Which public adapters are exposed and how errors are presented | Add, Query, Compare, Meld, and Help are verified multi-adapter vertical slices; Distill and Elaborate share typed multi-adapter paths. Help's Store-free `list`/`describe` query owns discovery while terminal syntax stays interface-owned. Compare Run/Open/Refresh use neutral execution and session owners with no synthetic Apply. Meld Start/Restart, exact Resolution turns, provider-free saved actions, and Apply all enter operation-owned application/runtime boundaries. Switch routes explicit CLI, interactive picker, and checkout-compatible selection through one typed locator/READ/CAS use case. Structural Atomize exposes saved/prepared/provider and focused analysis, exact review edits, unary reanalysis, in-place Apply, require-new Save As, and an explicit compound action through shared use cases; Summarize, Context Init, Embed, Search, Fit, Sever, Merge, and Dedup provide additional internal evidence | `CHARACTERIZED` | Remove the next CLI-to-TUI or interface-to-command policy dependency |
| `IMPORT-01` | Package import and operation assembly isolation | `SHARED CONTRACT` | Every packaged module; strict first audit for public Query, Search, quality finding, Add, Compare, Meld, structural Atomize, Atomize Grounding, Distill, Elaborate, Fit, Resolve, Dedup, and Help slices | Package/root imports have no external effects; selecting or importing one operation does not assemble unrelated operation adapters; Ground integration depends inward on an operation and is loaded only for its selected route | Public root re-exports and one-client compatibility remain; the Typer registry may retain eager command registration until its separate console migration | Fresh-process tests prove lazy real exports, Ground-blocked standalone imports, client import isolation, selected-method loading, and object identity. Help loads only its catalog/application modules and creates no Store. The current in-process registry and MCP projection expose sixteen shipped agent tools; the last clean installed-wheel gate proved the preceding fifteen-tool package graph and structural Atomize lifecycle | `VERIFIED` | Apply the same gate whenever another operation becomes a public slice; migrate eager Typer registration separately |
| `APP-02` | Context locator, readable catalog, targeting, and reach | `SHARED CONTRACT` + `SHARED MECHANICS` | add, atomize, audit, branch, checkout, checkpoint, check-conformance, chunk, clear, compare, contexts, delete, diff, distill, edit, embed, find-ambiguities, find-conflicts, find-duplicates, forget, ground, impact, import, list, lock, log, meld, merge, query, rationale, reference, revert, search, sever, share, show, status, summarize, switch, trace, translate, unlock, update | Capture current once; canonicalize existing locators; keep readable names, Grant metadata, lexical descendants, embedded traversal, and selected exact sets distinct | New-name operations, query-only routes, per-role authority, one-vs-many selection, and exact-vs-descendant defaults | Existing locators use the common resolver; readable catalogs, direct-Memory targets, exact/recursive presets, checked descendant projection, lazy item previews, and picker clipboard projection now share typed owners across the migrated command surfaces. Switch has a verified one-snapshot explicit-relative route and the complete picker implementation moved to `context_targeting.tui`; its command facade is behavior-free. Ground's physical workspace uses one real root and five real child Contexts, and its navigator reuses Context targeting without importing Switch or changing global current. Local `/contexts` descendants remain distinct from typed embeds/grants | `MIGRATING` | Finish the remaining operation-by-operation operand/reach audit and add authority-aware Ground typed-reference projection; remove behavior from remaining legacy picker/resolver facades |
| `APP-03` | Authority, disclosure freeze, and freshness revalidation | `SHARED CONTRACT` | Every operation that reads, transfers, derives from, or mutates Context/Memory/Profile material; initially the `APP-02` set plus init, init-study, profile, provider, rename, ground, undo, and redo where their resources require it | Required authority is checked before disclosure or mutation; frozen identities are revalidated at Apply; interfaces cannot infer permission from visibility | Required permissions (`READ`, `CREATE`, `UPDATE`, `COMBINE`, `EXPORT`, `SAVE_*`, and others), local-vs-granted targets, and lock set | Strong slice evidence in Add, Query, Search, Sever, Embed, Context Init, Merge, Meld, and Switch. Switch distinguishes visible QUERY-only rows from READ-selectable public names, reauthorizes Grants under the registry lock, and binds local target UID/digest plus current state in one CAS | `CHARACTERIZED` | Build a permission/effect table per operation and test every pre-provider and pre-Apply failure boundary |
| `SEM-01` | Provider trust and semantic-execution boundary | `SHARED CONTRACT` + `OPERATION OWNED` strategy | atomize, audit, check-conformance, compare, distill, elaborate, eval, find-ambiguities, find-conflicts, find-duplicates, fit, forget, ground, impact, meld, query, rationale, search, sever, summarize, translate, update | Freeze and authorize input before provider construction; one failed staged run publishes no partial result; provider output crosses a strict decoder | Execution strategy, whole-frame requirement, batching, reconciliation, schema, and retained dialogue | Shared semantic-execution plan plus verified Query, Summarize, Sever, Search, and Fit slices; Ground Fit now exhaustively combines Rule–Example with Context, vertical, and peer checks over exact frozen inputs. Distill and Elaborate also prove strict whole-frame direction-specific decoding, Elaborate enforces a nonempty candidate set, and oversized live misses construct no provider | `CHARACTERIZED` | Inventory every remaining provider factory/`complete()` route and link it to an explicit strategy and pre-disclosure test |
| `RESOLVE-01` | Frozen Resolution lifecycle | `SHARED CONTRACT` + `OPERATION OWNED` condition and solver | merge conflict decisions; Meld issue turns; Fit Resolve; Dedup; future clarification where its contract overlaps | Bind exact item and choice UIDs to one frozen artifact revision; reject duplicate, unknown, or capability-crossing submissions; required work gates readiness where the operation resolves a complete set; Resolution does not Apply | Conflict detector, incremental-vs-complete readiness, deterministic/interactive/semantic solver, candidate verification, minimum-change metric, persistence, and mutation | [Resolution lifecycle](resolution-lifecycle-design-rationale.md) implements the pure contract for structural Merge, saved Meld issue turns, public [Fit repair](resolve-fit-repair-design-rationale.md), and [deterministic Dedup](dedup-design-rationale.md). The smaller Merge/Dedup/Resolve workbench now retains and exactly projects that frozen case, then revalidates individual and bulk UI outcomes before review and Apply; operation adapters still own solver, authority, persistence, and mutation | `CHARACTERIZED` | Keep clarification and the richer saved-session model separate; do not extract a common semantic solver from operations that only share revision-bound decision mechanics |
| `CACHE-01` | Hidden prepared-analysis lookup and projection | `SHARED CONTRACT` with operation-owned proof | atomize, compare, distill, elaborate, meld directional, meld resolution, sever, summarize, update | Authority and complete frozen evidence precede lookup; a valid hit avoids provider construction; exact/equivalent/projected reuse must preserve the requested operation contract; hidden installations do not become visible sessions before invocation | Cache key, graph/scope equivalence proof, safe subset projection, result decoder, and user-visible origin | Study prewarm registry covers seven persisted artifact kinds. [Compare](compare-session-lifecycle-design-rationale.md) proves its public path uses production exact/equivalent/projected ordering and materializes an exact hidden receipt without provider construction; safe projections remain explicitly unsaved. Meld verifies exact, ancestor-equivalent, descendant-subset, relative scope, empty-parent, and saved follow-up reuse without provider construction. Atomize performs exact hidden lookup after Context capture and before lazy provider construction. Distill and Elaborate have tested exact-only lookup ports but no installed hidden artifacts | `CHARACTERIZED` | Continue the same case matrix for the other persisted artifacts; add Distill/Elaborate only after an exact hidden-receipt format is designed |
| `SESSION-01` | Saved analysis, opaque revision, and CAS lifecycle | `SHARED CONTRACT` + `OPERATION OWNED` schema | atomize, audit, compare, fit, forget, ground, impact, meld, review, sever, translate, update; investigate search and quality-report sessions separately; Distill and Elaborate are currently process-local `N/A` variants | Interfaces receive opaque snapshots/tokens; create/open/revise/apply revalidate one exact revision; stale or repeated actions cannot publish a second effect | Persisted schema, which decisions are durable, session visibility, resume behavior, and whether analysis is saved at all; Fit is an immutable create-only derived receipt, while Distill/Elaborate currently publish no visible session | Atomize saved resume, exact prepared first-use materialization, provider creation, stale rejection, refresh, and final-only Save As share typed boundaries without changing its pair schema. [Meld](meld-session-lifecycle-design-rationale.md) requires the `open` version for every saved mutation and permits only exact Apply recovery. [Compare](compare-session-lifecycle-design-rationale.md) exposes targetless Run/Open/Refresh with exact analysis-payload CAS. Ground now has physical creation/edit/open, operation-local Distill/Elaborate/Fit freezing, immutable Fit receipts, and local Undo. Existing legacy names remain transitional readers only and cannot be dual-written with a physical workspace | `MIGRATING` | Install hidden Distill/Elaborate receipts, migrate the writable conversational workbench, then remove the legacy Ground repository and whole-frame digest contract |
| `READ-REPORT-01` | Sessionless read-report lifecycle and content-free Recents | `SHARED CONTRACT` + operation-owned execution/view | summarize, trace, rationale, find-duplicates, find-ambiguities, find-conflicts | A completed recent retains only canonical target/range identity; selection revalidates the attempt and current authority, execution remains operation-owned, and closing never mutates a Context or creates a visible analysis session | Source freezing, cache eligibility, provider use, report document, clipboard scope, process-local responses, and downstream handoffs remain operation-owned | [Read Report lifecycle](read-report-lifecycle-design-rationale.md); all six operations project the neutral Operation Launcher, legacy Memory-report attempts remain readable, focused tests cover content exclusion, deduplication, stale rejection, and adapter rerun, and the [180×52 capture set](screenshots/read-report-recents-20260816/README.md) verifies representative Summarize and finder paths | `CHARACTERIZED` | Keep Audit/Compare outside this sessionless family and apply the same content-free/revalidation gate to any future read report |
| `APPLY-01` | Review, no-op, final approval, and materialization | `SHARED CONTRACT` + `OPERATION OWNED` decision model | atomize, branch, checkout -b, chunk, clear, delete, distill, edit, embed, search materialization, forget, ground, import, init, lock, meld, merge, profile mutations, reference, rename, revert, sever, share, translate materialization, undo, unlock, update | Review does not mutate; final action is explicit; no-op is represented deliberately; Apply consumes the exact reviewed/frozen state and returns a complete result | Whether exact argv is shown, required vs optional items, bulk choice, custom content, idempotence, and destination creation/update semantics | [Ownership-aware policy](ownership-aware-application-review-design-rationale.md) is application-owned; Merge, Update, Forget, Sever, and Meld are verified across their applicable local/authority, no-op or all-KEEP, CAS/freshness, failure publication, and operation-unit Undo/Redo cases. Meld additionally requires the opened opaque version and accepts only the reconstructable reviewed predecessor for exact Apply recovery. [Atomize](atomize-application-boundary-matrix.md) verifies recorded all-preserved completion, AS-IS audit, opaque workbench revision, in-place compensation, and final-only require-new Save As with exact retry | `MIGRATING` | Continue the next operation slice without treating operation-owned no-op or creation semantics as universal |
| `EFFECT-01` | Receipt, checkpoint, operation-unit Undo/Redo, and rollback | `SHARED CONTRACT` with explicit applicability | add, atomize, branch, checkout -b, chunk, clear, delete, distill Apply, edit, embed, forget Apply, ground edits, import, init, meld Apply, merge, reference, revert, sever Apply, translate materialization, update Apply; plus profile/config/protection mutations requiring a documented non-Undo boundary | A success receipt covers the complete command effect; multi-Context effects form one unit; failed publication exposes no partial success; Undo support or exclusion is explicit | Checkpoint payload, crash-recovery mechanism, irreversible external effect, and whether an operation is intentionally outside Undo | Semantic Apply Undo rationale and several vertical slices; Atomize in-place verifies one-checkpoint Undo/Redo, synchronous receipt compensation, late success, and exact interrupted recovery. Ground workspace genesis is an atomic six-Context require-new batch and intentionally outside both Undo stacks. Later Ground edits share one root-scoped command identity; local LIFO Undo restores the touched lane plus root, rejects drift, advances revision, and is excluded from global `mem undo` | `MIGRATING` | Decide Ground-local redo and complete the repository-wide durable-write/crash-window inventory |
| `TUI-01` | Endpoint setup and frozen operation shape | `SHARED MECHANICS` | atomize, audit, compare, embed, meld, merge, sever, update; investigate branch, check-conformance, distill, forget, query, search, and translate where they select multiple roles or modes | One visible role-based setup; selection returns process-local typed values only; setup performs no provider call or durable mutation; final operation validation remains authoritative | Role symmetry/direction, selectable catalog, independent per-role range/memory focus, fixed endpoint, fresh result name, and modes | Merge, Audit, Compare, Update, and Meld use `interfaces.tui.components.endpoint_setup`. Meld verifies mode-dependent A+B→C/A→B roles, exact direct-Memory focus, independent descendant reach, and a confirmed process-local new Result name without provider, session, or durable creation | `MIGRATING` | Remove the shared screen's remaining `commands.tui_primitives` dependency, then characterize Atomize without changing its measured Study flow |
| `TUI-02` | Selection, focus topology, back navigation, and writable-input protection | `SHARED MECHANICS` | Every interactive operation: atomize, audit, branch, checkout, compare, contexts, delete, diff, distill, elaborate, embed, eval, fit, forget, ground, help, history/log, impact, import, init, meld, merge, profile, provider, query, rationale, reference, revert, review, search, sever, share, summarize, switch, translate, update, plus interactive variants discovered by the callable catalog | Shared focus controller reports movement/boundary/consumption; Escape has an operation-owned exit path; Backspace is not stolen from writable input; visible frame order determines traversal | Surface topology, defaults, labels, operation actions, and editor validation | Shared core, frame, focus, scroll, input, choice, targeting, and selection owners are inventoried below. The full Context picker now has one neutral implementation used by Switch, Context browsing, Ground direct selection, and command-hosted consumers; Switch-specific selection-to-request translation lives in its interface adapter. Several unrelated command-hosted screens still remain | `MIGRATING` | Complete the prompt-toolkit application/import inventory, then retire parallel mechanics by component family rather than by visual resemblance |
| `TUI-03` | Resolution workbench | `SHARED MECHANICS` + `OPERATION OWNED` semantic projection | atomize, audit findings where answerable, forget, meld, merge, review, sever, update; inspect impact and quality findings as read-only/adaptive variants | Viewer, conditional Responses, Items, optional Save Location, and To Do share topology; required items gate Apply; response and final action remain separate; workbench never bypasses application validation | Detail document, issue/conflict types, choices, custom-response permission, whole-set strategy, Apply effect, and saved schema | A 4,757-line legacy shell and a smaller new interface workbench coexist; adapters target both generations | `MIGRATING` | Characterize feature parity, select one owner, migrate one operation family at a time, and prohibit new operation-local Resolution shells |
| `TUI-04` | Exact command review | `SHARED CONTRACT` + `SHARED MECHANICS` | embed, ground, import, merge, Profile rename/removal; Search SHOW is a receipt-only read action | One interface-neutral immutable argv/effects value and one escaped renderer; a consequential final review uses focused `Enter`, cancellation publishes nothing, and writable editing cannot coexist with approval | Ground and Search dispatch allowlisted argv; Import, Profile, Embed, and Merge apply an adjacent frozen typed plan/action; `A` remains a legacy alias where already published | [Consumer-boundary rationale](exact-command-review-consumer-boundary-design-rationale.md); type identity, rendering, every execution binding, cancellation, Embed single-use application, Merge plan/conflict application, and the read-only Search SHOW receipt are verified | `VERIFIED` | Keep the row closed under every new consumer; audit application policy separately under `APPLY-01` |
| `TUI-05` | Semantic/read-only Viewer, clipboard, and result verification | `SHARED MECHANICS` | compare, diff, distill, elaborate, fit, help detail, impact, query, rationale, review reports, search, show, summarize, trace; Resolution operations reuse only the compatible Viewer layer | Neutral report chrome; Memory objects use Memory styling; focused section/cross-section copy is deterministic; read-only exit never mutates | Typed document/detail model, citations, Fit judgment/freshness vocabulary, Distill evidence links, Elaborate verification state, diff semantics, source-member grouping, and copy scope exposed by the operation | Fit, Distill, and Elaborate have typed shared-Viewer projections and PTY evidence. Show now has a typed direct-inspection result and independent plain presenter, but no current TUI route; several other command-hosted viewers retain local rendering | `MIGRATING` | Inventory the remaining compatible result surfaces without copying another operation's semantic document |
| `HELP-01` | Stable operation discovery and interface-specific syntax | `SHARED CONTRACT` + `SHARED MECHANICS` | All 60 operations | One canonical summary/flow/execution/effect/range record; CLI, TUI, Python, and agent projections do not invent semantic meaning | CLI flags/forms, runtime authority/cache receipts, detailed algorithms, and operation rationale | The 60-entry Help catalog has complete structural coverage and one Store/provider-free application query. Plain/TUI Help, immutable Python DTOs, and the version-1 agent/MCP tool use that query; successful machine calls report `effect: NONE`. Collapsed wide rows and compact stacked rows retain their tested interface layouts. Final human English/Korean wording review remains separate | `VERIFIED` | Keep catalog and adapter coverage closed while completing per-operation wording review |
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
| `TUI-C01` | Core terminal mechanics | `memcommit.interfaces.tui.core` and `.components` | Add, Distill, Elaborate, Embed, Fit, Meld, Merge, Query, and Summarize surfaces; command-hosted screens also import selected interface helpers | Theme semantics, safe text layout, frame/scroll/input mechanics, buffer/activity helpers, and layered back-key grammar do not own operation meaning | Screen topology, labels, validation, and actions remain operation-owned; `commands.tui_primitives` is now an import-only compatibility facade | `CHARACTERIZED` | Migrate remaining command-hosted consumers by component family and prohibit new `interfaces` → `commands` imports |
| `TUI-C02` | Frame and focus surfaces | `interfaces.tui.components.frame` and `.focus` | Add, Endpoint Setup, Embed, Merge, Query, semantic/read-only viewers, shared workbenches, and numerous legacy command screens | Frames compose top-to-bottom; focus movement reports moved/boundary/consumed; visible order determines traversal | Each screen defines its own visible surfaces and activation meaning | `CHARACTERIZED` | Add family-level traversal and Escape/Backspace parity tests, then close duplicate focus-index implementations |
| `TUI-C03` | Scrolling, choice, input, background turn, and clipboard mechanics | `interfaces.tui.components.scrollable_pane`, `.horizontal_choice`, `.in_frame_input`, `.multiline_input`, `.background_turn`, and `.plain_text_clipboard` | Add and Query are the broadest new consumers; Distill, Elaborate, Fit, and both Resolution shells use shared clipboard mechanics, the Ground Fit turn uses shared background lifecycle, and Merge/Resolution use shared wrapped-row scrolling | Cursor/viewport mechanics, writable-input protection, one background-turn lifecycle, pure anchored/whole text projection, and plain-text clipboard injection remain presentation-only | Choice content, validators, cancellation policy, provider lifecycle, and copied semantic scope stay with the operation adapter | `CHARACTERIZED` | Classify remaining legacy helpers against these owners; keep typed semantic-section selection in the Viewer adapter rather than the writer component |
| `TUI-C04` | Context targeting and generic selection | `memcommit.context_targeting.tui` and `memcommit.selection.tui` | Add, Context Init, Distill, Embed, Query, Summarize, Endpoint Setup, Switch, Ground Save Location and workspace navigation, Context browsing, Memory reports, and the migrated command-hosted operations | Context tree, exact/descendant reach, checked selection, lazy direct-item preview, direct-Memory target identity, common selection rendering, and picker clipboard preserve typed state contracts | Readable catalogs, authority, role availability, defaults, materialization meaning, clipboard scope, and executable receipts remain operation-owned. Ground New uses the shared parent locator only to compose an uncreated exact root, while its navigator projects the real fixed workspace plus local `/contexts` descendants and changes only its process-local active surface; Switch alone maps a selection to global current | `MIGRATING` | Audit exact empty/Grant/query-only variants and remaining targeting facades |
| `TUI-C05` | Endpoint Setup | `interfaces.tui.components.endpoint_setup` | Merge, Audit, Compare, Update, and Meld; Meld adds tested mode-dependent roles and confirmed new Result naming | Modes and named roles produce one process-local typed draft; fixed roles, independent per-role descendant reach, exact direct-Memory focus, and confirmed-but-uncreated names are visible; Context, reach, or mode changes clear stale hidden state; cancellation performs no provider call or durable write | Authority, caller-owned projection loading, name validation, plan preparation, cache/session identity, and Apply remain outside the component; its legacy command path is an import-only facade | `CHARACTERIZED` | Extend only through the interface owner and keep operation-specific authority/cache/Apply policy outside the component |
| `TUI-C06` | Exact command review | `interfaces.tui.components.exact_command_review` | Embed, Merge, Ground/Profile command screens, and the new Resolution workbench | One immutable argv/effects identity and one escaped projection back focused Enter approval; cancellation publishes nothing | Allowlisted dispatch and adjacent frozen plan/application policy remain operation-owned; Search SHOW is explicitly receipt-only | `VERIFIED` | Require the same consumer audit before admitting another operation |
| `TUI-C07` | Semantic and read-only viewers | `interfaces.tui.viewers.semantic` and `.read_only` | Distill, Elaborate, Fit, Summarize, and Merge use the new owners; Compare, Rationale, Trace, and Share retain compatible command-hosted consumers | Neutral report chrome, Memory styling, focus anchoring, scrolling, and deterministic focused/whole-document copy are shared mechanics | Typed documents, citations, evidence linkage, verification vocabulary, relation grouping, diff meaning, and copyable semantic scope remain operation projections | `MIGRATING` | Use the ordered Distill/Elaborate terminal evidence while building the remaining operation-by-operation viewer/copy matrix |
| `TUI-C08` | Context-summary and Resolution workbenches | `interfaces.tui.workbenches.context_summary` and `.resolution` | Summarize and Distill use Context Summary; Merge, Dedup, and Resolve use the frozen-case deterministic workbench; Meld and other saved/process-local reviews invoke the relocated Resolution Session owner | A workbench composes shared frame, focus, response/choice, Viewer copy, and wrapped-scroll mechanics into a stable topology without owning domain decisions; deterministic UI outcomes re-enter their exact frozen `ResolutionCase` | Required/optional meaning, comments/drafts, provider turns, conflict schema, no-op, save location, Apply, and CAS remain operation-owned; the richer Session model is not collapsed into the choice-only deterministic model | `CHARACTERIZED` | Reuse lower components across both shells while keeping optional/comment/provider semantics separate until genuine model parity exists |
| `TUI-C09` | Direct item placement | `interfaces.tui.components.direct_item_placement` | Embed only in the new operation packages | Exact item selection and placement remain typed and read-only until operation submission | Its present single-operation use does not yet prove a repository-wide component contract | `PROVISIONAL` | Reuse only when a second operation demonstrates the same invariant; otherwise keep it operation-adjacent |
| `TUI-C10` | Operation launcher | `interfaces.tui.components.operation_launcher` | Atomize, Audit, Compare, Ground, Impact, Meld, Review, Sever, Update, and Trace/Rationale recent adapters | A frozen catalog supports sort, grouping, filtering, detail, orientation, and one pinned action; the shared screen returns entry/action identity only and owns no argv, persistence, provider, cache, or session meaning | Saved-session reopen/New receipts remain in the session adapter; Ground always renders the launcher and interprets New as a physical Context-root Save Location; recent-run rerun and new-target meaning remain with each read-report adapter; `commands.session_picker` is import-only | `CHARACTERIZED` | Retire remaining session vocabulary from sessionless callers without changing durable session formats |
| `TUI-A01` | Per-operation TUI adapters | `interfaces.tui.operations.<operation>` | Add, Audit, Compare, Context Init, Distill, Elaborate, Embed, Fit, Help, Meld, Merge, Query, Summarize, Switch, and Update | Each adapter translates typed application values to shared mechanics and must not become a second application service | Help freezes application discovery once, then adds CLI-only forms, grouping, focus, and responsive layout. Switch's adapter translates a frozen picker result to one request while locator, READ, load, and CAS stay application/runtime-owned. Meld's setup, saved-session screen, Compare report renderer, Resolution Session shell, Save Location control, and semantic-detail renderer resolve through neutral/interface owners | `CHARACTERIZED` | Inventory Sever, Atomize, and the remaining smaller command-hosted screens without reintroducing reverse imports |

## Operation-family coverage

Every visible operation appears exactly once below. Families are investigation
units, not proposed universal implementations.

| Family | Operations | Primary contracts to audit first | Important non-uniformity |
| --- | --- | --- | --- |
| Context orientation and browsing | contexts, list, pwd, show, status, switch | `APP-01`–`APP-03`, `TUI-02`, `TUI-05`, `HELP-01` | Switch alone mutates the process-global current pointer through its typed READ/CAS use case. Show freezes one live authorized direct-inspection snapshot for CLI/Python/agent projections; the other routes are reads, and `pwd` deliberately loads no Context |
| Direct deterministic Memory/Context mutation | add, chunk, clear, delete, edit, embed, reference | `APP-01`–`APP-03`, `APPLY-01`, `EFFECT-01`, `TUI-02`, `TUI-04` | Embed/reference retain identity relationships; clear/delete are destructive; Add is a batch append |
| Namespace, Profile, distribution, and protection administration | branch, checkout, config, import, init, init-study, lock, profile, provider, rename, share, shell-init, unlock | `APP-01`–`APP-03`, `APPLY-01`, `EFFECT-01`, `TUI-02`, `TUI-04`, `CONFIG-01` | New-name operands must not use the existing-Context locator contract; Share is external; shell-init is read-only output; several mutations are intentionally outside Context Undo |
| History, recovery, lineage, and explanation | checkpoint, diff, log, rationale, redo, revert, trace, undo | `APP-01`–`APP-03`, `EFFECT-01`, `TUI-02`, `TUI-05` | Rationale may infer; Undo/Redo operate on command units; Diff/Log/Trace are read-only; Revert is reviewed mutation |
| Semantic read and report operations | audit, check-conformance, compare, elaborate, find-ambiguities, find-conflicts, find-duplicates, fit, impact, query, review, search, summarize | `APP-01`–`APP-03`, `SEM-01`, `SESSION-01`, `TUI-01`–`TUI-03`, `TUI-05` | Elaborate returns unverified process-local proposals; Fit saves an immutable derived receipt without changing Ground; Query has ordinary, granted, and reference routes; Review stages responses but never applies; Impact may be a handoff rather than the owning operation |
| Semantic staged mutation or derived materialization | atomize, distill, forget, ground, meld, sever, translate, update | All application, semantic, cache/session/apply/effect, and TUI contracts that apply | Forget mutates Source; Sever creates a new Result; Meld reconciles semantically; Update is directional; Ground has separately approved bindings and commands; Atomize is Study-deferred |
| Deterministic staged structural reconciliation | merge | `APP-01`–`APP-03`, `SESSION-01`, `APPLY-01`, `EFFECT-01`, `TUI-01`–`TUI-05` | Merge shares review mechanics but must remain provider-free and must not acquire Meld-style custom semantic reconciliation |
| Evaluation and discovery | eval, help | `APP-01`, `SEM-01` or `HELP-01` respectively, `TUI-02`, `CONFIG-01` | Eval changes evaluation ledgers rather than Context content; Help is a stable catalog projection and never executes an operation |

## First convergence queue

The queue is ordered by risk of duplicating a safety contract during ongoing
migration, not by visual prominence. Exact command review identity and the
second Endpoint Setup consumer have crossed their earlier gates; their
remaining work is recorded in the ledger rather than repeated as unfinished
milestones.

1. **`TUI-01` Remaining endpoint capability gate.** Characterize the exact
   new-Context naming and mode-dependent active-role contracts required by
   Atomize and Meld before extending the shared component or retiring their
   legacy setup paths.
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

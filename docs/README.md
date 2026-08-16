# Documentation language and evidence convention

Memcommit's implementation notes, design rationales, command contracts, and
decision histories are written in English so they can be reviewed and reused
consistently.

Non-English text is retained only when it is evidence rather than explanatory
prose:

- verbatim user or study-task source material;
- bilingual source records whose filename explicitly says `original-and-*`;
- linguistic examples whose exact wording is part of a semantic boundary or
  regression case.

These quotations are not treated as an exception to the English documentation
contract: the surrounding explanation, labels, and conclusions remain in
English. Task-specific material is intentionally not translated or normalized
until the task fixtures and study wording are finalized, because an early
rewrite could destroy the exact ambiguity, scope, or malformed wording that a
semantic operation is meant to preserve and analyze.

When a design decision excludes a behavior, defers it, or accepts a prototype
limitation, the relevant focused `*-design-rationale.md` document must state
the reason and the remaining boundary. A conversation-only explanation is not
considered sufficient design history.

## Multilingual Memory and explanation-language research TODO

- [`multilingual-memory-and-explanation-language-design-rationale.md`](multilingual-memory-and-explanation-language-design-rationale.md)
  records why Memory authoring language, semantic analysis language,
  explanation language, interface language, and translation target are
  distinct roles. The current shared result-workbench demo deliberately
  retains English explanatory output while preserving source evidence
  verbatim; global and per-command language selection remains deferred
  research rather than partial localization.

## Clipboard result contract

- [`mem-ls-design-rationale.md`](mem-ls-design-rationale.md) defines
  `ls/list --copy` as synchronized clean-or-annotated text and typed-result
  output,
  `ls/list --paste` as frozen read-only replay, clipboard-overwrite
  invalidation, and the query-only non-disclosure boundary.
- [`mem-add-paste-design-rationale.md`](mem-add-paste-design-rationale.md)
  preserves the distinct interactive bracketed-paste intake contract for
  `mem add --paste`.

## Directional update contract notes

- [`task-1-naming-contract.md`](task-1-naming-contract.md) fixes the distinct
  names and authority roles of the task-owned change source, granted
  `campus-wiki`, nested query-only details view, and
  `task-1-campus-authority` owner.
- [`mem-impact-update-design-rationale.md`](mem-impact-update-design-rationale.md)
  defines impact preview, validated local application, per-owner checkpoints,
  applied-result receipts, exception rollback, deterministic diff, and the
  mutation boundary.

## Profile authority and query sessions

- [`mem-profile-design-rationale.md`](mem-profile-design-rationale.md) defines
  whole-store selection, inventory, and atomic Profile import.
- [`mem-import-design-rationale.md`](mem-import-design-rationale.md) defines
  typed Profile, Context-tree, and Memory import; stable identity, closed
  reference scope, collision behavior, excluded source history, and the
  relationship to Study initialization.
- [`profile-authority-grant-design-rationale.md`](profile-authority-grant-design-rationale.md)
  defines ordinary authority ownership, permissioned task views, frozen
  scopes, nested override precedence, grant CRUD, and the Task 1--3 topology.
- [`query-only-research-prototype.md`](query-only-research-prototype.md)
  distinguishes current authority-granted query views from the supported
  legacy `QueryContextRef` storage model.
- [`query-session-design-rationale.md`](query-session-design-rationale.md)
  defines optional task-owned visible Q/A transcripts, `SESSION_LOG`, explicit
  replay, source/grant freshness, and non-retention of authority source text.

## Context namespace migration

- [`mem-write-protection-design-rationale.md`](mem-write-protection-design-rationale.md)
  defines bare current-Context lock/unlock, frozen recursive Context sets,
  direct-Memory locks, the active Profile's upper read-only policy, shared
  store-level enforcement, and branch and rename identity behavior.
- [`mem-command-dependency-design-rationale.md`](mem-command-dependency-design-rationale.md)
  records the shared locator, loader, source-binding, creation/deletion,
  catalog, display, and revert boundaries used across `mem` commands, plus the
  privacy and authority differences that remain intentionally separate.
- [`context-locator-design-rationale.md`](context-locator-design-rationale.md)
  defines canonical names, explicit relative existing-Context locators, the
  one-current-snapshot rule, and the rollout boundary between lookup operands
  and newly declared names.
- [`mem-embed-placement-design-rationale.md`](mem-embed-placement-design-rationale.md)
  defines explicit before/after direct-item anchors, the flagless Child/Into/gap
  form, exact-command review, and neighbor-bound concurrency checks.
- [`context-scope-cli-design-rationale.md`](context-scope-cli-design-rationale.md)
  defines the shared `-d/--direct` and `-r/--recursive` presets, precise
  role/axis overrides, and the direct-only operation boundary.
- [`mem-rename-design-rationale.md`](mem-rename-design-rationale.md) defines
  the internal UID-preserving slash-subtree relocation primitive; typed
  reference, current-state, checkpoint, Ground, and translation continuity;
  the query-only non-access boundary; graph freshness; exception rollback; and
  the remaining crash-journal limitation. Public `mem rename` is the Profile
  display-name operation described by the Profile rationale.

## Translation contract

- [`mem-translate-design-rationale.md`](mem-translate-design-rationale.md)
  defines direct-only candidate scope, provider/curated same-UID catalogs,
  exact semantic targets, edit/import/review, explicit materialization,
  concurrency validation, checkpoint lineage, and the query-only privacy
  boundary.
- [`study-fixture-bundle-design-rationale.md`](study-fixture-bundle-design-rationale.md)
  defines English-canonical task/authority Profile pairs, same-UID Korean
  views, permissioned bilingual query views, deterministic runtime identities,
  grant manifests, and the atomic six-Profile import boundary.
- [`study-fixture-spreadsheet-design-rationale.md`](study-fixture-spreadsheet-design-rationale.md)
  defines the paired 20-tab review workbook, native review checkboxes,
  diff-only color cues, formula/read-back verification, and the boundary
  between spreadsheet annotations and runtime Memory authority.

## Semantic provider contract

- [`semantic-provider-design-rationale.md`](semantic-provider-design-rationale.md)
  defines provider/model separation, Codex-compatible default behavior,
  the explicit Codex Luna-low preset, loopback Ollama and fixed-route
  OpenRouter adapters, strict-schema and no-fallback invariants, query-only
  routing boundaries, Qwen evaluation, and the remaining durable provenance
  migration.

## Distribution and application-boundary plan

- [`distribution-boundary-and-architecture-understanding-plan.md`](distribution-boundary-and-architecture-understanding-plan.md)
  records the evidence-led distribution, public-interface, application,
  domain, infrastructure, configuration, provider-security, and incremental
  vertical-slice plan.
- [`mem-summarize-design-rationale.md`](mem-summarize-design-rationale.md)
  defines the read-only Summarize semantic contract and shared understanding
  unit.
- [`summarize-application-boundary-matrix.md`](summarize-application-boundary-matrix.md)
  records the first verified internal TUI-independent use case plus its plain
  and TUI console adapters, callable and provider-security matrices,
  compatibility evidence, and remaining public API gates.
- [`tui-component-architecture-design-rationale.md`](tui-component-architecture-design-rationale.md)
  records the interface-owned frame, focus, scrollable-pane, and Viewer
  hierarchy, the no-facade consumer migration, Summarize routing contract,
  wheel check, and ordered PTY evidence.

## Semantic evaluation harness

- [`semantic-eval-harness-design-rationale.md`](semantic-eval-harness-design-rationale.md)
  defines corpus roles, the ambiguity leave-one-out calibration, implemented
  V1--V6 stage contracts, deterministic gates, provider/model provenance,
  replay ledgers, latency measurement, and observed Sol/Luna/Qwen score and
  timing distributions. It also records the frozen 12-case holdout, Qwen V2's
  36/36 result, Luna V2/V6 quality and latency tradeoff, and why that holdout
  is now consumed evidence rather than a reusable V7 test. Profile-wide
  pipeline selection remains preferred over case routing. These steps do not
  change production mutation boundaries.
  The same note now records the frozen 37-case base and 75-case composite
  operation-gate pilots, short/long Task 1--3 slices, the 200-case intermediate
  ceiling, and the staged path to all 1,306 study Memories. It also records the
  locked Task 2 150-versus-150 relation-discovery ladder, full Sol/Qwen
  one-shot failures, structure-only decomposition, oracle-band diagnostic, and
  why the reviewed relation groups are not a 22,500-pair answer key.
- [`task2-classification-diagnostic-design-rationale.md`](task2-classification-diagnostic-design-rationale.md)
  defines the oracle-group evidence axes, deterministic five-band projection,
  exact group-ID coverage, retained timings, and the boundary that those axes
  do not yet have independently reviewed Gold.
- [`task2-portable-semantic-harness-design-rationale.md`](task2-portable-semantic-harness-design-rationale.md)
  defines the 26/50/100/138 Task 2 scale ladder, reviewed hypergroup versus
  atomic-pair boundary, source-anchored V3 and candidate-verifier V4 contracts,
  Sol/Qwen/Luna comparison gates, timing and interruption limits, and the
  revision-locked failure-steering loop toward the full 150-versus-150 target.
- [`semantic-duplicate-eval-design-rationale.md`](semantic-duplicate-eval-design-rationale.md)
  defines the host-first exact/surface split, strict four-way semantic stage,
  observed Qwen/Luna/Sol calibration timing, and the independent duplicate
  holdout still required before a generalization claim.

## Ground iteration plan

- [`ground-ticker-iterative-flow-todo.md`](ground-ticker-iterative-flow-todo.md)
  records the staged one-to-approximately-twenty Example demonstration, the
  missing reviewed binding-refresh action, and the later exact hidden-receipt
  boundary without treating a case count as automatic Ground completion.

## Atomize contract notes

- [`atomize-public-python-api-design-rationale.md`](atomize-public-python-api-design-rationale.md)
  defines the stable saved/prepared/provider and exact-Memory analysis
  projection, versioned review edits, unary reanalysis, in-place Apply,
  require-new Save As, compound action, retry recovery, and stale conflict.
- [`atomize-agent-tool-design-rationale.md`](atomize-agent-tool-design-rationale.md)
  defines the seven strict structural lifecycle actions, explicit
  cache/provider/effect reporting, newest-version chaining, stateless final
  recovery, registry/MCP projection, and companion Skill boundary.
- [`semantic-result-workbench-design-rationale.md`](semantic-result-workbench-design-rationale.md)
  generalizes the result-explanation hierarchy shared by bounded semantic
  operations: compact counts, what was understood, what happened, what remains
  unresolved, and traceable representative or boundary cases. It also records
  why that shared presentation must not flatten operation-specific semantics
  or mutation authority.
- [`semantic-resolution-workbench-design-rationale.md`](semantic-resolution-workbench-design-rationale.md)
  defines the shared dynamic list/detail/comment frontend used by Meld and
  Atomize and the read-only planned-change projection used by Update. It keeps
  provider, persistence, readiness, and application semantics in
  operation-owned controllers, leaves Ground separate, and reserves only the
  adapter boundary for future Reconcile.
- [`mem-atomize-design-rationale.md`](mem-atomize-design-rationale.md) defines
  atomicity, source grounding, preview/application boundaries, and lineage.
- [`mem-atomize-workbench-design-rationale.md`](mem-atomize-workbench-design-rationale.md)
  defines the aggregate analysis, typed issue workbench, stable resume, and
  explicit reanalysis contract.
- [`memory-review-shell-design-rationale.md`](memory-review-shell-design-rationale.md)
  records the interaction language shared with ambiguity review while keeping
  each operation's persistence, source arity, and mutation boundaries distinct.
- [`mem-review-conversational-grounding-design-rationale.md`](mem-review-conversational-grounding-design-rationale.md)
  records the atomize grounding-session contract for multi-turn
  comment–implication–confirmation loops modeled on grounding in ordinary
  human communication. Shared turn-lineage may be reused, but named Ground's
  Goal–Rules–Memories frame remains separate from Resolution Workbench.
- [`atomize-grounding-agent-tool-design-rationale.md`](atomize-grounding-agent-tool-design-rationale.md)
  defines the strict five-action agent contract over the public Grounding
  facade, its provider and mutation boundaries, JSON projection, registry/MCP
  path, and remaining concurrency limitation.
- [`mem-atomize-grounding-screen-captures.md`](mem-atomize-grounding-screen-captures.md)
  indexes exact tested CLI captures for the workbench, awaiting, resumed,
  corrected ready, and applied states.

## Meld contract note

- [`mem-meld-usage.md`](mem-meld-usage.md) is the canonical user-facing
  command guide. It standardizes “atomic meld” as informal shorthand for the
  implemented issue-scoped directional flow under
  `mem atomize --evaluate`; documents Context-wide directional
  `mem meld [INCOMING] --into BASELINE` and its current-baseline convenience
  `mem meld --from INCOMING`; distinguishes both from symmetric
  `mem meld LEFT_PEER RIGHT_PEER`; and reserves `--to` for a future explicit
  symmetric result destination.
- [`mem-meld-design-rationale.md`](mem-meld-design-rationale.md) distills the
  directional and symmetric authority modes; explains issue/all/remaining
  turn scope; documents both implemented Context workbenches and the atomize
  flow's lossless directional/issue projection, where a unary source candidate
  becomes an ephemeral one-Memory `INCOMING` Context frame against its bound
  `BASELINE`; and records shared turn-lineage, relation, provenance, approval,
  and mutation contracts.

## Compare contract note

- [`mem-compare-design-rationale.md`](mem-compare-design-rationale.md) defines
  targetless ordered peer comparison, durable source-bound analysis,
  exhaustive N:M relations, automatic reanalysis after source changes, and
  the boundary between a static Compare view and later grounding/Meld turns.

## Disclosure and delivery contract

- [`selective-curation-design-rationale.md`](selective-curation-design-rationale.md)
  defines the common whole-frame keep/transform/drop analysis and Resolution
  report used by Forget and Sever while keeping their mutation, grant, and
  materialization boundaries separate.
- [`mem-sever-design-rationale.md`](mem-sever-design-rationale.md) defines the
  local disclosure-review artifact and its strict separation from sending.
- [`mem-share-design-rationale.md`](mem-share-design-rationale.md) defines the
  grant-backed Task 3 receiver endpoint, exact Sever-output requirement,
  receiver-owned Memory copy, consent digest, and idempotent delivery receipt.

## Saved-work launcher contract

- [`mem-session-picker-design-rationale.md`](mem-session-picker-design-rationale.md)
  defines the read-only launcher shared by Ground, Meld, Atomize, and Compare;
  stable selection receipts, post-selection freshness checks, recently modified
  versus durable time semantics, Context rather than invented project grouping,
  and the planned Review adapter after Review gains multi-record persistence.

## Per-Memory provenance and explanation

- [`mem-search-artifact-design-rationale.md`](mem-search-artifact-design-rationale.md)
  defines the shared Find/ordinary-Query candidate frame for visible Memories,
  saved sessions, operation records, checkpoint-derived trace events, and
  cached rationales while preserving Profile and grant boundaries.
- [`mem-trace-rationale-design-rationale.md`](mem-trace-rationale-design-rationale.md)
  defines current and retained historical Memory selection, the shared
  read-only terminal picker, content-lineage evidence levels, recorded versus
  inferred rationale, atomize attachments, and query-only non-disclosure.

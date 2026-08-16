# Distribution boundary and architecture-understanding plan

## Status

Active long-term plan and evidence ledger. Most packaging, platform, and
architecture migration remains unimplemented. Completed or characterized
slices are named explicitly below; an unmarked target remains planning only.

## Progress ledger

Update this table in the same change that crosses a gate. Do not use an
estimated percentage: each state must be backed by a linked design record,
test, installed-artifact check, or operation trace. A row marked `VERIFIED`
means its stated completion gate passed, not merely that implementation code
exists.

Last reviewed: 2026-08-16.

| Workstream | Current state | Evidence now recorded | Next gate |
| --- | --- | --- | --- |
| Target application boundary | `VERIFIED` for nine principal slices | The seven prior Summarize/Add/Sever/Find/Query slices retain their boundaries. Distill and Elaborate now add shared CLI/TUI/public/agent/MCP paths, exact Ground adapters, ordered terminal evidence, and installed-wheel discovery. | Keep their no-session/no-persisted-cache limits explicit while completing human Help review. |
| Console composition and TUI isolation | `VERIFIED` for read-only and first writable slices | Summarize proves independent typed read presenters. Add, Query, Distill, and Elaborate have independent interface projections; their shared registry imports only the public client and agent adapters. | Continue moving command-hosted screens behind the same console composition boundary. |
| Callable and operation matrices | `GENERATED; INITIAL ROUTE CURATION` | `operation-consistency-matrix.md` catalogs all 59 visible operations against cross-operation contracts. The [mechanical callable catalog](callable-catalog-design-rationale.md) inventories 8,306 source callables across 607 modules and resolves every Help operation to a CLI entry plus statically observed application, TUI, Python, agent, and boundary evidence. The separate [reviewed classification](operation-route-classification.json) conservatively records 13 `CLOSED`, 3 `MIXED`, and 43 `UNREVIEWED` routes; none is called `LEGACY` or `N/A` without route evidence. | Curate the contract-affecting callable subset, reconcile the conflicting Meld records, and trace `UNREVIEWED` operations before assigning stronger states. |
| Package import and operation assembly | `VERIFIED` for the first public-slice audit | `package-import-boundary-design-rationale.md` separates application isolation from Python package loading. Lazy real root/API exports, operation-selected client assembly, Ground-blocked fresh imports, 112 public/agent/MCP regressions, and an outside-checkout installed-wheel check preserve the existing names and object identity. | Apply `IMPORT-01` to each newly public slice; keep Typer command registration as a separate console migration. |
| Shared TUI component system | `MIGRATING` | Shared core, components, viewers, and workbenches now serve Distill's Context Summary plus semantic Viewer and Elaborate's semantic Viewer, in addition to the earlier adapters. Command-hosted and legacy Endpoint/Resolution screens remain explicit parallel paths. | Capture the new operation traces, then close duplicate mechanics component family by component family. |
| Operation Help catalog | `CHARACTERIZED` for structural coverage | All 59 visible operations share one interface-neutral summary, flow, execution, effect, range, and use-case record. Distill and Elaborate are structurally covered, but their complete human wording and wide/compact rendering review remains in progress. | Finish per-operation Help review and keep runtime forms aligned with Ground and public routes. |
| Semantic provider trust boundary | `DISCOVERY RECORDED` | The existing provider-neutral protocol, allowlisted adapters, endpoint restrictions, strict output handling, and known command-local calls are documented here and in the provider rationale. | Inventory every provider connection/completion path and prove the pre-disclosure gates. |
| Typed runtime configuration | `DISCOVERY RECORDED` | Typed semantic accessors exist, but duplicated defaults and operation-local overrides remain. | Freeze the key catalog, precedence, validation bounds, secret sources, and effective per-request snapshot. |
| Distribution baseline | `CHARACTERIZED` | Package discovery now includes `memcommit*`; a built wheel contained the new interfaces and existing subpackages, and an isolated `uvx --from <wheel>` environment resolved both `mem` and the frame component from site-packages. | Repeat the complete smoke suite from a clean checkout and record cross-platform artifact results. |
| Authoritative wheel | `MIGRATING` | One locally built wheel passed installed `mem summarize --help` and import-origin checks outside the source directory; this is evidence for package completeness, not yet a release claim. | Pass the Phase 2 clean-checkout gate and supported-platform matrix. |
| Summarize application slice | `VERIFIED` | `summarize-application-boundary-matrix.md` records the typed request/result, terminal-free runtime, local/READ-granted scope, independent plain/TUI adapters, 93 focused tests, 1,258 partitioned TUI-consumer tests, an installed-wheel smoke test, and the ordered PTY trace. | Keep public export separate; use a second operation to prove input/review/effect boundaries. |
| Sever application slice | `VERIFIED` | `sever-application-boundary-matrix.md` records typed analysis and complete saved-session lifecycle requests/results, terminal-independent application/runtime execution, authority-before-cache/provider ordering, opaque review CAS, destination validation, prepared-analysis provider prohibition, require-new checkpointing, idempotence, and Source preservation across 53 focused tests. | Keep public export and physical TUI relocation separate; use the completed Find Search slice as the next adapter-parity evidence. |
| Find application slice | `VERIFIED` | `find-search-application-boundary-matrix.md` records application-owned search and materialization contracts, terminal-independent CURRENT/HISTORY execution, source-before-provider ordering, query-view privacy, a reviewed COPY/REFERENCE write, authority and source locks, require-new publication, rollback, and Source preservation. Plain CLI and the workbench share search execution; the TUI submits materialization through the separate typed write use case. | Keep dialogue and answer synthesis separate; carry the proven split into Query. |
| Ordinary Query application slice | `VERIFIED` | `query-answer-application-boundary-matrix.md` records the typed question/result, readable-corpus Store adapter, authority/source freeze before provider construction, whole-frame preflight, one structured completion, host-owned citations, provider-free empty and over-budget failures, no terminal output, and Source preservation. Both terminal adapters consume the same typed runtime response. | Keep its future public export and agent mapping distinct from granted publication authority. |
| Granted Query application slice | `VERIFIED` | `granted-query-read-publication-design-rationale.md` records typed catalog/answer reads, provider-before-concealed-Source ordering, post-provider route and Source revalidation, a zero-write unpublished-turn plan, and a separate `SESSION_LOG`/Source/CAS publication port. `query-public-python-api-design-rationale.md` keeps that token internal while defining high-level success as read plus requested publication. | Preserve the active-Profile boundary until authority locking can be injected without process-global state. |
| QueryContextRef application slice | `VERIFIED` | `query-reference-application-boundary-matrix.md` records a typed local query-only request/result, provider-before-concealed-Source ordering, exact UID/name/language loading, one provider turn, zero durable effects, and the independent safe CLI projection. | Preserve it as a separate legacy route unless a reviewed authority migration replaces its storage contract. |
| Query vertical operation package | `VERIFIED` | `query-operation-package-design-rationale.md`, `query-tui-interface-design-rationale.md`, `query-cli-interface-design-rationale.md`, `query-public-python-api-design-rationale.md`, `query-agent-adapter-design-rationale.md`, and `query-callable-boundary-matrix.md` record all three application/runtime pairs, CLI/TUI/agent projections, infrastructure-owned provider composition, public typed results/errors, tests, and ordered PTY evidence. | Treat the Python/CLI/TUI/agent slice as complete; keep concrete MCP/network hosting separate. |
| Current Context orientation slice | `VERIFIED` | `mem-pwd-design-rationale.md` records a terminal-independent typed result, Store adapter, one-line CLI presenter, missing-state behavior, and local/virtual-pointer tests. It deliberately loads no Context and creates no Store. | Reuse the application result for a future Python or agent adapter only after that public contract is versioned; this micro-slice does not replace the next cache/effect slice. |
| Add vertical operation package | `VERIFIED` | `mem-add-application-and-tui-design-rationale.md`, `add-public-python-api-design-rationale.md`, `add-agent-adapter-design-rationale.md`, and `add-callable-boundary-matrix.md` record the typed ordered batch, active CREATE Grant boundary, CAS, one checkpoint, independent CLI/TUI, stable public results/errors, strict version-1 agent projection, non-retryable mutation failures, validated skill, regressions, and ordered PTY trace. | Treat the Python/CLI/TUI/agent slice as complete; keep concrete MCP/network hosting and skill installation separate. |
| Context Init application slice | `VERIFIED` | `context-init-application-boundary-matrix.md` records typed request/result and creation-plan values, independent exact-name TUI and CLI presenters, terminal-free Store execution, exact/parent checkpoint parity, reuse, collision, and current-CAS rollback across 198 focused regression tests. | Keep `mem init --study` routed to a separate future Study Init application; use the Sever slice to finish semantic cache/review/Apply composition. |
| Atomize application slice | `VERIFIED` | `atomize-application-boundary-matrix.md` records saved/prepared/provider and focused open, exact response/Output edits, unary reanalysis, both final directions, checkpoint/receipt recovery, and compound application; `atomize-public-python-api-design-rationale.md` records the complete stable projection. | Keep pair-shaped conflicts, Grant mutation, and conversational Grounding outside this structural contract. |
| Update application slice | `NOT STARTED` | Trace scope and ordering are planned. | Begin after a safer second slice or an independently recorded blocker justifies changing the order. |
| Meld application slice | `TUI BOUNDARY CHARACTERIZED` | Setup and saved-session presentation live under `interfaces.tui.operations.meld`; Compare rendering and the Resolution Session now have neutral/interface owners, and an automated package scan prohibits every `interfaces` → `commands` import. Typed receipts preserve symmetric/directional, exact-Memory, descendant, new-Result, Grant, and prewarm projections. Provider, cache, session lifecycle, and Apply remain in the existing application/command path and are not claimed as extracted. | Characterize the application/runtime slice while preserving directional, graph-subset, projection, authority, cache, and Apply cases. |
| Remaining operation slices | `IN PROGRESS` | Find search/materialization and all three Query execution families now have verified internal boundaries and Query's terminal interface ownership is complete. Find dialogue and the remaining operations are still named in the trace order. | Use reverse-import evidence to select the next safe non-Study extraction. |
| Public Python API | `VERIFIED` for the reviewed operation slices | `MemCommitClient` exposes reviewed Query, Add, Meld, Fit, Distill, Elaborate, Atomize Grounding, and the complete structural Atomize lifecycle over one frozen Store root. Operation rationale notes record typed results/errors, provider and mutation lifecycles, fresh-process import isolation, and focused parity tests; structural Atomize additionally passes installed-wheel effect/recovery smoke. | Keep unreviewed actions such as Ground Distill materialization unavailable; agent adapters remain projections rather than second facades. |
| Machine-readable and agent adapters | `VERIFIED` for Query, Add, Meld, structural Atomize, Atomize Grounding, Distill, Elaborate, and Fit | Eight strict version-1 adapters call the public client. The frozen registry and MCP projection expose them without terminal or command imports. A fresh installed wheel exposes all eight through official MCP stdio discovery and runs provider-free structural Atomize saved open, response edit, Output planning, in-place Apply, Save As, and exact retries. Structural Atomize reports cache/provider/effect explicitly and has a validated companion Skill; Distill/Elaborate return `effect: NONE`; Elaborate also returns `verification: UNVERIFIED`. | Provider-backed semantic invocation from an installed artifact and actual Skill installation remain separate gates. |
| Cross-platform infrastructure | `NOT STARTED` | Platform-sensitive capability categories are listed in Phase 5 and the Infrastructure section. | Complete the inventory, then test implementations on actual supported hosts. |

Allowed states are deliberately evidence-oriented:

- `NOT STARTED`: only intent or ordering is recorded;
- `DISCOVERY RECORDED`: observed current-state evidence exists, but the baseline
  or contract has not been frozen;
- `DOCUMENTED`: the intended contract and completion gate are recorded, but
  implementation conformance has not yet been proven;
- `CHARACTERIZED`: current inputs, effects, failures, and compatibility are
  protected by a trace and tests;
- `MIGRATING`: an implementation change is in progress but has not crossed its
  completion gate;
- `VERIFIED`: the row's completion gate has passed with recorded evidence;
- `BLOCKED`: a concrete external dependency or unresolved decision prevents
  the next gate and is named in the row; and
- `DEFERRED`: work is intentionally postponed to protect a measured or unstable
  contract, with an explicit condition for resuming it.

Focused operation notes and tests hold detailed evidence. This ledger remains
the concise index of what is actually complete and what comes next.

## Objective

Make the current MemCommit CLI installable and runnable from an isolated
distribution, initially through `uv tool install`, without requiring a source
checkout or an editable installation. Use that work to build an evidence-based
understanding of the repository, then improve internal boundaries only where a
real operation trace demonstrates the need.

The near-term goal is not a rewrite. It is to establish a trustworthy
distribution boundary around the behavior that already exists.

## Working principles

1. **Preserve behavior before reorganizing it.** An installed wheel must be
   tested against the same command contracts, durable state, caches, receipts,
   and review/application boundaries as a source checkout.
2. **Do not require a whole-repository review before shipping the first valid
   distribution.** Packaging work should inspect only the dependency paths
   needed to prove that the installed artifact is complete.
3. **Learn the architecture through vertical slices.** Trace one operation
   from CLI entry through storage and verification rather than reviewing files
   in directory or size order.
4. **Extract common code only after confirming common meaning.** Similar UI or
   code shape is insufficient. At least two operations must share the same
   invariant, lifecycle, and failure boundary before a common component is
   introduced or expanded.
5. **Keep packaging fixes and architecture changes separately reviewable.** A
   packaging failure must not become an excuse for unrelated refactoring.
6. **Treat discoveries as deliverables.** Record ownership, dependencies,
   durable effects, and unresolved boundaries as they are learned so that the
   same investigation is not repeated later.

## Target application boundary

The installed Python package remains one implementation and one distribution.
"Python library" does not mean a second copy of an operation beside the CLI or
TUI. It means a small, stable public facade over the same application use case
that every other entry point invokes.

```text
Public interfaces
  - Python API
  - CLI
  - TUI
  - agent skill/tool adapter
            |
            v
Application use cases
            |
            v
Domain core <--> infrastructure ports
                    |
                    v
             infrastructure implementations
```

This runtime dependency direction is paired with a separate Python package
loading boundary. A lightweight package root and public export surface must not
assemble unrelated operation integrations before the caller selects an
operation. `package-import-boundary-design-rationale.md` owns that cross-cutting
contract; it does not create a second operation implementation.

The target is one operation implementation with several input and presentation
routes. A CLI command, Python caller, interactive workbench, and agent tool must
not independently reconstruct an operation's authority, cache, provider,
receipt, or application rules.

In this note, *application layer* means MemCommit use-case orchestration. It is
distinct from prompt-toolkit's `Application` UI object.

### Illustrative, non-normative package layout

The following tree is a direction for discovery and incremental extraction,
not a frozen directory contract:

```text
memcommit/
  domain/
    context.py
    memory.py
    authority.py
    cache_policy.py
  operations/
    query/
      ordinary_application.py
      ordinary_runtime.py
      granted_application.py
      granted_runtime.py
      reference_application.py
      reference_runtime.py
    atomize/
    update/
    meld/
  infrastructure/
    persistence/
    providers/
    config/
    platform/
  interfaces/
    console/
      router.py
      terminal.py
    cli/
    tui/
    agent/
  entrypoint.py
  api.py
  bootstrap.py
```

The normative target is the ownership and dependency direction described in
this document: one operation use case, domain-owned invariants, explicit
infrastructure capabilities, and multiple thin public interfaces. Exact
directory names, file granularity, class-versus-function choices, and whether
the public facade is `api.py`, a client package, or another small surface may
change as vertical traces provide evidence.

An implementation must not move files merely to resemble this tree. A proposed
deviation is acceptable when it preserves the dependency and trust boundaries,
keeps one source of operation policy, remains testable through the same ports,
and is recorded in the relevant operation matrix or rationale. A structural
change that weakens those invariants requires a separately reviewed design
decision rather than an undocumented convenience.

### Console composition root and adapter isolation

The installed `mem` executable remains one console host, but CLI rendering and
interactive TUI behavior are separate adapters. They must not invoke each
other or reconstruct an operation. Both translate to the same application use
case. A small console router selects the presentation route, and a composition
root supplies its concrete dependencies.

```text
mem entry point
      |
      v
composition root / bootstrap
      |
      v
console router
  |              |
  v              v
TUI adapter   plain or JSON CLI adapter
  |              |
  +-------+------+
          v
   application use case
```

`bootstrap` means startup composition, not operation policy. It may know the
concrete application services, Store and provider adapters, CLI renderer, TUI
controller, config source, and terminal-capability implementation because its
job is to construct and connect them. No application, domain, infrastructure,
plain presenter, or TUI presenter imports bootstrap. During the Typer rollout,
an operation command is the entry boundary that asks bootstrap for its runner;
the console-script root can assume that responsibility after command
registration is factory-based.

The console router owns only route selection. Presentation mode is independent
from semantic operands such as Context and reach:

- automatic mode opens an operation's TUI only when both input and output are
  interactive terminal streams;
- `--plain` explicitly chooses the stable scripted renderer, including inside
  an interactive terminal;
- `--tui` explicitly requires the interactive renderer and fails before the
  application callable is executed when terminal capability is absent; and
- machine-readable JSON remains a separately versioned explicit route once its
  contract is implemented.

Framework-owned `--help` and version handling are not operation execution. A
semantic option such as `--recursive` does not silently become a presentation
choice: an agent can add `--plain`, while a person can retain the Viewer for an
explicit Context or reach. This separates operation meaning from host
capability and keeps both routes testable.

TTY detection is an injected terminal capability, not a domain rule or a
collection of command-local `isatty()` checks. Production inspects the process
streams lazily, while tests supply an explicit capability snapshot. A TUI may
use prompt-toolkit `Input` and `Output` objects for deterministic testing, but
it remains a terminal interface; terminal independence belongs to the
application and Python API paths.

Adapter isolation has these dependency rules:

- a CLI adapter parses argv and renders plain or machine output, but does not
  import or execute a TUI adapter;
- a TUI adapter owns layout, key handling, focus, scrolling, and process-local
  input drafts, but does not import CLI commands;
- both adapters consume typed application requests, views, actions, results,
  and errors;
- provider calls, authority, cache policy, receipts, durable session writes,
  CAS, and Apply remain below the adapters; and
- the composition root is the only module allowed to select concrete siblings
  and wire them together.

The current console-script target `memcommit.cli:app` remains a compatibility
boundary during migration. Do not change packaging and interactive routing in
the same first step. The existing module may temporarily expose the assembled
Typer application while construction moves behind a factory; a later isolated
distribution change may point the console script at an explicit entry-point
function after clean-wheel parity is proven.

### First console-composition slice: Summarize

Summarize is the first complete read-only console slice. Its TUI is not a
second implementation of Summarize: it projects the already verified typed
result into the shared semantic Viewer. The implemented order was:

1. freeze `mem summarize` direct/recursive scope, output, error, empty-frame,
   Grant, provider-laziness, and plain-copy behavior;
2. move terminal escaping and plain rendering into interface-owned modules;
3. extract frame, focus, scrollable-pane, and semantic-Viewer contracts from
   `commands`, then migrate every existing consumer of those moved contracts;
4. add a Summarize TUI adapter that maps `SummarizeResult` directly to a typed
   `SemanticViewerDocument`, without parsing CLI text or calling the provider;
5. compose the application callable and the two independent presenters through
   an injected terminal-capability router; and
6. verify source and wheel execution, forced-route failures before execution,
   existing consumer behavior, and the ordered real-PTY interaction.

Summarize now follows the shared Context-scope preset contract. Omission and
`-d/--direct` select only directly owned ordinary Memories. `-r/--recursive`
expands every readable lexical descendant in the frozen public catalog and
follows permitted embedded Context edges, de-duplicating Context UIDs. The
typed application request retains those two traversal axes independently so a
future interface does not have to reconstruct them from terminal spelling.
This semantic correction is characterized separately from the later
console-composition refactor.

Summarize's `--copy` route is presentation-only. It copies the already
revalidated understanding document to the operating-system clipboard, creates
no structured mutation stage or MemCommit artifact, and never re-enters the
application use case. Clipboard implementation remains an interface concern
for the eventual composition root.

Only the component family needed for the Summarize slice moved initially. The
later Add trace justified moving the existing multiline-input and in-frame
input/edit contracts into `memcommit.interfaces.tui.components`; every existing
consumer of those moved contracts now imports that owner directly. Exact-name,
fixed-choice, and other semantic controls retain their current owners until an
operation trace demonstrates the same invariant. Each next slice should reuse
the extracted hierarchy and add only a genuinely shared missing interaction
family rather than introduce another operation-local layout system.

### Domain core

The domain core is executable Python code, not documentation. It owns
MemCommit-specific models, invariants, deterministic decisions, and state
transforms that can be evaluated without opening a terminal, reading a host
path, or connecting to a provider. Representative responsibilities include:

- Context, Memory, relation, proposal, and receipt value semantics;
- exact-coverage, disposition, provenance, and source-grounding validation;
- deterministic application of an approved Atomize, Update, Meld, Forget, or
  Sever result to an in-memory state;
- pure authority decisions over already loaded Grant and ownership facts; and
- pure cache-compatibility and projection-safety decisions over already frozen
  graph identities, scopes, revisions, and operation contracts.

CRUD is not itself one layer. A Context mutation invariant belongs to the
domain core; deciding when a use case may perform the mutation belongs to the
application layer; loading and saving the Context belongs to infrastructure;
parsing `mem add` or displaying the result belongs to an interface adapter.

### Application use cases

The application layer is also executable Python code. It owns the ordered,
failure-atomic procedure for completing one user-visible operation. For an
Atomize request, the eventual use case should coordinate steps such as:

1. freeze the requested Source identity and revision;
2. load and evaluate the required authority before disclosure;
3. ask the cache policy whether an exact or projected artifact is safe;
4. connect to a provider only when the frozen request cannot be satisfied by
   valid retained evidence;
5. validate the semantic result with the domain core;
6. retain the compatible session and hidden receipt;
7. accept an explicit reviewed action; and
8. revalidate CAS and authority before publishing the durable mutation.

It returns typed outcomes rather than printing terminal text or raising a
Typer-specific exit. The application layer decides *that* a valid hidden
receipt must be saved, for example, while an infrastructure implementation
decides *how and where* the bytes are saved safely.

### Infrastructure

Infrastructure is executable integration code, not a general `utils` bucket.
It implements explicit capabilities required by application use cases and is
where MemCommit touches the host environment or an external service. Its
expected scope includes:

- Context, Profile, Grant, checkpoint, and current-state persistence;
- saved operation sessions, hidden cache artifacts, receipts, and CAS objects;
- provider transports, authentication/configuration lookup, timeouts, and
  response acquisition;
- filesystem path resolution, atomic replacement, durability sync, file modes,
  interprocess locking, symlink/reparse-point handling, and platform-specific
  behavior;
- clocks, identifier generation, and similar nondeterministic capabilities
  when a use case needs them; and
- package-resource loading and other installed-artifact access.

Infrastructure must not decide the semantic meaning of an operation. For
example, a receipt store may atomically persist a typed receipt, but it must not
decide whether a graph subset is safe for Meld reuse. A provider adapter may
send a bounded request and decode its transport response, but it must not
silently invent a different batching or completeness contract.

This split also makes cross-platform work tractable: application code asks for
an atomic save or lock through a named capability, while macOS, Linux, and
Windows implementations satisfy that capability without scattering OS checks
through command modules.

### Semantic provider trust boundary

LLM execution is a distinct infrastructure trust boundary because it can
disclose Memory content to another process or network service, consumes
credentials and paid capacity, accepts untrusted output, and can create
security-relevant logs or error text. It must remain separately reviewable even
when it shares the ordinary application request/result path.

The application use case owns whether a semantic call is permitted and what
frozen disclosure frame, operation contract, schema, and budget it needs. A
provider port exposes the smallest provider-neutral completion capability. A
provider infrastructure adapter alone owns transport, credentials, endpoint
validation, request encoding, response size limits, timeout enforcement, and
transport-level provenance. Domain code, CLI commands, and TUI shells must not
open their own HTTP or subprocess route to a model.

The boundary must preserve or add the following controls:

- evaluate authority and cache eligibility before provider connection and
  before loading content that the selected route may not receive;
- allowlist provider kinds and validate endpoints against each provider's
  explicit network policy, including the existing loopback-only Ollama rule;
- acquire secrets from a dedicated secret source rather than durable Context,
  session, receipt, ordinary config output, or command argv;
- never record prompts, completions, credentials, authorization headers, or
  provider error bodies in ordinary logs; retain only the minimum safe audit
  metadata required by the operation contract;
- enforce bounded request, response, context, output, and time budgets;
- require the operation-owned schema and local semantic validator to accept a
  response before it can become retained analysis;
- prohibit silent provider, model, schema, repair-call, or fallback changes;
- freeze provider identity and effective non-secret settings once per
  application request; and
- attach safe provider/model/settings provenance to the hidden receipt where
  the durable schema supports it.

Prompt and output-schema definitions remain operation-owned contracts. They may
be grouped in dedicated semantic modules, but moving them into a transport
adapter would let infrastructure change operation meaning. The existing
[`semantic-provider-design-rationale.md`](semantic-provider-design-rationale.md)
remains the detailed provider contract and must be updated when this migration
changes or supersedes one of its decisions.

Current code already contains useful pieces of this boundary: a
provider-neutral `SemanticProvider` protocol, typed provider identity/run
metadata, allowlisted adapters, a loopback-only local endpoint, response-size
limits, strict JSON handling, and redacted HTTP failures. The remaining
architecture work must preserve those controls while removing command-local
connection/call paths and making pre-disclosure application gates uniform.

### Typed configuration boundary

Runtime configuration needs a versioned, typed ownership model; it must not
become a bag of string keys or scattered numeric literals. Configuration is
loaded by infrastructure, validated against code-owned safety rules, and frozen
as one immutable effective snapshot supplied to an application request.
Operations should not independently read environment variables, the home
directory, or mutable global config after that snapshot is created.

The configuration catalog must record, for every setting:

- stable key and owning capability;
- type, unit, documented default, and allowed range or enum;
- source and precedence, such as explicit API/CLI input, process environment,
  user config, or built-in default;
- whether it is secret, sensitive, or safe to show and retain in a receipt;
- the operations and provider adapters that consume it;
- whether it may vary per request or requires a new process/provider snapshot;
  and
- validation, compatibility, and migration tests.

Numeric tunables such as provider timeout, context allocation, output budget,
operation aggregate budget, retry count, and concurrency may be configuration
when a documented use case needs them. Their units and safe bounds remain code
contracts. Semantic invariants and security policy are not configurable merely
because they contain a number: exact coverage, required authority, no-fallback
behavior, maximum security ceilings, output-schema versions, and receipt/CAS
requirements remain code-owned rules.

Secrets use a separate `SecretSource`-like capability backed initially by the
process environment or an approved company secret mechanism. The typed
non-secret config snapshot may state that a credential is available, but must
not contain, print, serialize, or receipt the credential value.

The present typed semantic accessors are a useful starting point. The later
inventory must resolve duplicated defaults in `memcommit.config` and
`memcommit.semantic_provider`, and operation-local mutations such as Meld's
aggregate timeout adjustment inside its command module. The goal is one
effective value with one owner and visible provenance, not making every
constant user-configurable.

### Public interfaces and adapters

Each public route translates its own input into the same typed application
request and translates the returned outcome for its audience:

- the Python API exposes a stable import and typed request/result facade;
- the CLI parses argv, selects interactive or non-interactive presentation,
  renders results, and maps typed failures to exit codes;
- the TUI gathers selections and reviewed actions and renders state, but does
  not independently call providers, evaluate caches, or publish mutations; and
- an agent skill/tool adapter exposes a bounded schema and maps it to the same
  use case, directly or through an explicitly supported machine-readable CLI
  route.

The application layer does not call the public Python facade. The dependency
direction is the reverse: the Python facade, CLI, TUI controller, and agent
adapter all call the application use case.

### Cross-interface invariants

Migration must preserve these invariants:

- every public route uses the same application path for the same operation;
- authority is checked before provider connection or unauthorized disclosure;
- cache reuse and projection follow the same frozen compatibility policy from
  every route;
- cache origin, projection, provider execution, and frozen inputs remain
  traceable through the operation's hidden receipt;
- a failed semantic batch, validation, persistence step, or CAS check publishes
  no partial durable operation result;
- only the reviewed proposal may be applied, after current authority and source
  revision are revalidated;
- existing session and receipt compatibility is retained unless a separately
  reviewed migration changes the durable contract; and
- equivalent CLI, TUI, Python, and agent requests produce equivalent typed and
  durable outcomes, allowing only presentation-specific differences.

### Required traceability matrices

Progress needs two levels of matrix rather than one manually maintained list
of thousands of undifferentiated helpers.

The **complete callable catalog** is generated mechanically from the source so
private functions do not disappear from review. It records at least module and
qualified name, visibility/export status, current inbound references,
decorators, signature, and source location. Generated data is inventory, not an
architectural conclusion.

The current generator, limitations, and reproducibility contract are recorded
in [`callable-catalog-design-rationale.md`](callable-catalog-design-rationale.md).
The checked-in outputs are
[`generated/callable-catalog.jsonl`](generated/callable-catalog.jsonl), its
compact
[`generated/callable-catalog-summary.json`](generated/callable-catalog-summary.json),
and the 59-row
[`generated/operation-route-catalog.md`](generated/operation-route-catalog.md).
Its curated state is loaded from
[`operation-route-classification.json`](operation-route-classification.json),
which must cover exactly the same canonical operation set. Mechanical presence
and human-reviewed closure remain separate fields.

The **curated boundary matrix** classifies every callable that can affect an
external contract or cross a trust/durability boundary. It must include:

- public exports and intended Python API functions;
- CLI command handlers and TUI action/controller boundaries;
- application use cases and domain validators or mutators;
- authority and cache/projection decisions;
- provider connection and completion call sites;
- Context, session, receipt, cache, checkpoint, and config reads or writes; and
- subprocess, filesystem, network, clipboard, or other host-effect functions.

Pure private rendering and formatting helpers remain in the generated catalog
and may be classified by owning module unless a vertical trace shows that they
affect a contract. This keeps the curated matrix exhaustive at meaningful
boundaries without turning it into a stale hand-written symbol dump.

The callable matrix uses this shape:

| Callable | Current owner | Intended layer | Inputs/result | External effects | Authority/disclosure | Cache/receipt | Config/secrets | Callers | Evidence | Migration state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `module:qualname` | command, core, shared, or unknown | domain, application, infrastructure, or interface | typed or implicit | none or named effects | check and timing | read/write/project | keys and sensitivity | known routes | tests/trace/note | unclassified through verified |

Each semantic operation also has one summary row so reviewers can compare
whole workflows without reconstructing them from individual symbols:

| Operation | Entry points | Application request/result | Authority | Cache/projection | Provider contract | Session/receipt | Review/Apply/CAS | Durable writes | Config | Verification | State |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Summarize, then later slices | CLI, TUI where applicable, Python, agent | operation-specific types | required grants/ownership | exact and safe projection routes | schema, parser, budgets | visible and hidden artifacts | approval and freshness boundary where applicable | exact stores | effective snapshot fields | parity and failure tests | not started through verified |

Provider calls receive an additional security matrix because one operation may
have several call paths or provider routes:

| Operation/call site | Frozen disclosure frame | Pre-connection authority gate | Cache gate | Provider/endpoint policy | Prompt/schema version | Effective budgets | Secret source | Safe provenance/receipt | Failure and no-partial-publication tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Configuration receives a corresponding catalog:

| Key | Owner | Type/unit | Default | Precedence | Allowed range | Secret/sensitivity | Consumers | Receipt visibility | Tests/migration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Matrices change in the same commit as the boundary they describe. A renamed or
moved callable retains a link to its earlier qualified name until the relevant
vertical slice is verified, so progress does not disappear through refactoring.

### Incremental extraction rule

Do not begin by publishing a broad API over the current command functions. That
would freeze terminal output, TTY behavior, global store lookup, and
Typer-specific exits as accidental library contracts. For each vertical slice:

1. characterize the current behavior and durable effects with tests;
2. record its present dependencies, authority checks, cache paths, receipts,
   and failure boundaries;
3. extract one operation-specific application request/result and use case
   without changing behavior;
4. make the existing CLI and TUI invoke that use case;
5. expose the proven use case through the public Python facade and a
   machine-readable adapter; and
6. add the agent skill/tool mapping without reimplementing the operation.

Summarize is the first implemented candidate because it exercises READ and
Grant freezing, provider disclosure, strict result validation, source
freshness, and typed read-only return without touching a measured Study
operation. It deliberately does not prove cache, receipt, review, or durable
mutation boundaries. Atomize remains a later high-value slice after its
experiment is frozen. Common abstractions should be introduced only after a
second safe slice demonstrates the same meaning and failure boundary.

## Known starting evidence

- The project already declares `mem = "memcommit.cli:app"`, which is the
  correct console-script shape for `uv tool install`.
- A wheel can currently be built, but a clean `uvx --from <wheel> mem --help`
  run fails because manually enumerated setuptools packages omit newer concept
  packages. The observed build omitted 44 Python files under packages such as
  `context_targeting`, `selection`, `responses`, `semantic_execution`, and
  `study_prewarm`.
- Editable installs conceal this class of failure because imports resolve
  directly from the source checkout.
- The runtime, evaluation harness, developer commands, fixtures, and bundled
  assets do not yet have an explicit product-distribution boundary.
- Several operation-neutral packages are already being extracted, but some of
  them still import command/TUI modules. Those dependency directions should be
  documented before they are changed.

These observations establish the first tasks; they are not a conclusion that
all large modules or import cycles must be fixed before distribution.

## Phase 1: freeze the distribution baseline

### Tasks

- Record the supported Python versions and the initial supported host scope.
- Build a wheel from a clean repository state.
- Inventory every Python package, package-data resource, font/license asset,
  and fixture required by the installed runtime.
- Record which CLI commands are part of the user-facing product and which are
  developer or evaluation surfaces.
- Capture the current source-checkout behavior of a small, representative
  smoke suite before changing packaging metadata.

### Initial smoke suite

- `mem --help`
- one non-mutating command that reads an empty or isolated store;
- `mem init` followed by `mem add`, `mem status`, and a read-back;
- one cached/prewarmed operation path and its no-provider reuse path;
- one representative interactive entry point where a suitable TTY test is
  available;
- import of the intended public Python API, once that public surface is named.

All tests must use an isolated MemCommit data root and must not read or mutate a
developer's real `~/.mem` state.

### Completion gate

A baseline report identifies the expected commands and resources, the source
checkout result, and every known clean-install failure. No architecture
refactoring is required for this gate.

## Phase 2: make the wheel authoritative

### Tasks

- Replace the fragile manually maintained package list with package discovery
  or an equally complete declarative configuration.
- Define package-data inclusion explicitly and verify licenses and runtime
  assets inside the built wheel.
- Decide whether evaluation and developer-only modules remain in the default
  wheel, move behind an optional extra, or become a separate distribution.
  Make that decision from actual runtime imports rather than directory names.
- Remove dependencies that are not used by the selected runtime artifact, and
  document the dependency-version policy used for repeatable internal
  installation.
- Add an installed-wheel test that runs outside the repository so an editable
  checkout cannot satisfy missing imports or resources.
- Test both local artifact installation and the eventual internal-index form.

### Required user-facing installation contract

Development or local artifact:

```text
uv tool install /path/to/memcommit.whl
mem --help
```

Internal package index:

```text
uv tool install memcommit==<version> --index-url <internal-index>
mem --help
```

The exact internal command may change with company package policy, but the
installed `mem` command must not depend on the original source tree.

### Completion gate

From a clean, isolated environment:

- the wheel installs with `uv tool install`;
- `mem --help` starts successfully;
- the agreed smoke suite passes using only wheel contents;
- required resources can be loaded through package-resource APIs;
- uninstalling the tool does not delete the user's durable MemCommit data;
- the build fails if a required package or resource is omitted.

## Phase 3: build the architecture map through vertical slices

This phase may begin while packaging defects are being diagnosed, but it must
not silently expand a packaging change into a broad refactor.

### Trace order

1. **Summarize** — first read-only application extraction: READ/Grant
   freezing, bounded provider disclosure, typed return, and source freshness
   without a TUI or durable mutation. The focused record is
   [`summarize-application-boundary-matrix.md`](summarize-application-boundary-matrix.md).
2. **Second non-Study slice, to be selected from evidence** — exercise a cache,
   receipt, or durable-effect boundary that Summarize cannot prove while
   avoiding currently measured workflows.
3. **Atomize, after the experiment is frozen** — provider analysis, cache,
   session, hidden receipt, review, and application behavior.
4. **Update** — explicit Source/Target semantics, proposal review, CAS, and
   durable target mutation.
5. **Meld** — multiple directional and scope-dependent paths, cache
   projection, and relation reconciliation.
6. **Sever** — shared curation mechanics with deliberately different
   authority and materialization semantics.
7. **Find/Query** — retrieval, readable Context catalogs, query-only routes,
   and result materialization.

The order may change when a packaging blocker requires a different trace, but
the reason should be recorded.

### Vertical-slice record

Create or update a focused architecture note for each operation with:

| Field | What to record |
| --- | --- |
| Entry points | CLI command, library-call candidate, and interactive shell |
| Inputs | locators, selections, instructions, persisted session fields |
| Frozen state | Context graph, aliases, scopes, digests, provider contract |
| Execution | planning, cache lookup, provider calls, reconciliation |
| Outputs | proposal, report, receipt, result, hidden artifact |
| Durable mutation | files changed, CAS/lock boundary, rollback behavior |
| Verification | diff, read-back, cache-hit proof, relevant tests |
| Authority | read, derive, combine, save, accept, and mutation checks |
| Shared components | components actually reused and the invariant they own |
| Coupling findings | reverse imports, duplicated mechanics, hidden global state |
| Open limits | intentionally deferred behavior or unsupported platform cases |

### Completion gate for each slice

A future reader can identify where the operation begins, where semantic work
occurs, when cached evidence is valid, what becomes durable, and how completion
is verified without rediscovering the entire call graph.

## Phase 4: rank boundary improvements from evidence

After Summarize and at least one operation with a different cache, receipt, or
effect boundary have complete traces, classify findings into four queues:

1. **Distribution blockers** — missing modules, resources, metadata, imports,
   or entry-point failures. Fix these in the distribution work.
2. **Correctness or safety blockers** — state-location ambiguity, cache/receipt
   mismatch, locking, CAS, or authority errors. Handle these as focused design
   changes with their own tests and rationale.
3. **Confirmed shared mechanics** — identical invariant and lifecycle across
   two or more operations. Move these to the narrow owning concept package.
4. **Maintainability opportunities** — large files, naming, or dependency
   direction that does not currently break the distribution or operation
   contract. Record and defer unless it blocks the next vertical slice.

Priority is determined by observed behavior and dependency direction, not line
count alone.

## Phase 5: prepare, but do not conflate, the platform boundary

Cross-platform support follows the valid wheel; it is not achieved merely by
using `uv`. During the earlier phases, record every platform-sensitive use of:

- user data and configuration paths;
- file and directory permissions;
- interprocess locks;
- atomic replacement and durability sync;
- symlinks, junctions, and other reparse points;
- portable names and case-insensitive collisions;
- newline-sensitive byte digests;
- clipboard, shell integration, and terminal behavior.

The later Windows implementation should introduce shared platform adapters and
actual Windows CI. Packaging changes should not emulate Windows behavior with
scattered command-local conditionals.

## Proposed pull-request sequence

Keep the work reviewable in small, independently testable changes:

1. Add clean-wheel inspection and installed-artifact smoke tests that expose
   the present failure.
2. Correct package discovery and package-data inclusion until the tests pass.
3. Decide and enforce the runtime versus eval/dev distribution boundary.
4. Document the installed command, upgrade, uninstall, data-retention, and
   internal-index procedures.
5. Complete and verify the Summarize application-boundary record and preserve
   CLI parity without introducing a public API prematurely.
6. Select and extract one second non-Study slice, then rank the confirmed
   shared boundary issues.
7. After the active experiment is frozen, add the Atomize vertical-slice record
   before changing its behavior.
8. Add Update and Meld records, then rank their confirmed boundary issues.
9. Implement only the highest-priority confirmed boundary improvement in a
   separate change.
10. Begin the cross-platform adapter and Windows CI work under its own plan and
   acceptance criteria.

## Non-goals for the initial distribution work

- Rewriting the store, CLI, or TUI.
- Splitting every large file before a wheel can be installed.
- Eliminating every import cycle in the first packaging change.
- Designing one universal semantic-operation abstraction.
- Changing cache identity, receipt schemas, or saved-session compatibility
  merely to make modules look uniform.
- Moving durable receipts into an expendable OS cache directory.
- Claiming native Windows support before tests run on a Windows host.
- Publishing to a public package index before internal artifact behavior and
  ownership are agreed.

## Overall completion criteria

The plan is complete when:

- a versioned wheel is the tested source of the `mem` command;
- `uv tool install` provides a documented clean installation and upgrade path;
- installed behavior does not depend on the repository checkout;
- product, evaluation, developer, and package-data boundaries are explicit;
- the principal operations have incremental vertical-slice records;
- common-component changes cite the shared invariant that justified them;
- platform-sensitive assumptions are inventoried and routed to a separate
  cross-platform implementation plan;
- large-scale restructuring remains optional and evidence-driven rather than
  a prerequisite for distribution.

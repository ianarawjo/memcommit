# Summarize application-boundary matrix

## Status

The internal application and production-runtime extractions are implemented and
verified. `run_summarize` completes the use case through abstract ports, while
`execute_summarize` composes it with a real `MemoryStore` and injected provider
without Typer, prompt-toolkit, terminal output, or TUI state. The console host
lets the automatic/plain adapter execute the current or explicit Context
immediately, while explicit `--tui` lets the interactive adapter execute after
a process-local selection and then present the same typed result. These are
internal boundaries, not yet a stable public
Python API.

Last reviewed: 2026-08-25.

## Objective and non-goals

This slice extracts the Summarize orchestration and admits one narrow
Study-only exact-result lookup:

```text
freeze locator and READ-authorized source
  -> skip provider for an empty frame
  -> otherwise resolve one exact pinned Study artifact or perform one bounded semantic summary
  -> rebuild and revalidate the frozen source
  -> return a typed read-only result
```

It deliberately does not move shared provider implementations or Grant logic,
semantic-execution planning, or understanding models. It adds no ordinary
Profile-local cache, Summary session, public client facade, agent tool, review,
or Apply. The Study artifact stays in the pinned shared bundle and materializes
only the typed process-local result. Its CLI `--copy` route remains a
post-result plain-text presentation effect and creates no structured clipboard
stage.

Summarize is also the first complete console-composition slice. The existing
plain route and a new read-only semantic Viewer sit behind an injected console
runner and composition root. Automatic mode deliberately selects the
line-oriented execution route even in a TTY because the current-Context/direct
defaults already form an executable request; `--tui` explicitly selects the
broader Recent/target/range workbench. The application remains
independent of Typer, prompt-toolkit, and process-global terminal detection.
Atomize, Compare, and other semantic operations retain their operation
behavior while their imports of the extracted component contracts now use the
new interface owner.

The scope contract now uses the shared `-d/--direct` and `-r/--recursive`
presets. Omission selects direct. Recursive expands readable lexical public
names and follows embedded Context edges, while the typed request retains
`include_descendants` and `follow_embeds` independently. The authorized public
catalog is frozen before expansion; Grant attachment metadata never becomes a
hierarchy edge. UID de-duplication prevents a Context reached lexically and by
embed from entering the provider frame twice.

The Store-backed adapter temporarily imports the operation-neutral access
implementation from `memcommit.application.authority.access`. That module does not
import Typer or prompt-toolkit, but its package location is still a known
reverse dependency. Moving it is deferred until a second vertical slice proves
the same owner and lifecycle; this slice must not copy or partially migrate the
shared Grant rules.

## Package ownership

The canonical terminal-independent owners now live under
`memcommit.application.operations.summarize`. `application.py` owns the typed request,
frozen Source, provider-session protocol, freshness check, and read-only
result. `runtime.py` owns Store and Grant projection, exact Study lookup,
configured-provider composition, and the production execution adapters.
CLI, TUI, bootstrap, Distill, Ground, prewarm/eval, and other production
consumers import those operation-owned modules directly.

The historical `memcommit.summarize_application` and
`memcommit.summarize_runtime` paths remain behavior-free module-identity
aliases for import-order, monkeypatch, and serialized-global compatibility.
Importing `memcommit.application.operations.summarize` alone remains lazy. New production
code uses the canonical package paths; compatibility aliases do not become a
second implementation owner.

The console-specific adapters are now co-located under
`memcommit.adapters.console.commands.summarize`: `command.py` owns orchestration,
`presentation.py` owns plain typed-result output, and `workbench/` owns the
process-local setup, semantic Viewer projection, clipboard projection, and
interactive screen adapter. The former operation-specific CLI and TUI interface
paths are removed without facades. The shared Context-summary workbench remains
under `adapters.interfaces.tui.workbenches` because its mechanics are reused by
other operations; this relocation changes only Summarize adapter ownership.

This relocation changes physical ownership only. It does not alter frame
collection, direct/recursive axes, READ or Grant authority, provider timing,
Study exact-artifact eligibility, source revalidation, typed result or receipt
shape, console routing, clipboard behavior, or TUI interaction. The existing
ordered PTY evidence therefore remains valid without a screenshot refresh.

## Current dependency path

```text
Python production caller
  -> execute_summarize(request, store, provider_factory)
  -> run_summarize_with_store
       -> MemoryStoreSummarySourcePort
       -> run_summarize

mem summarize argv
  -> memcommit.adapters.console.commands.summarize.command.cmd
  -> resolve semantic scope and presentation mode
  -> AUTO becomes immediate plain execution; --tui alone opts into setup
  -> bootstrap builds ConsoleRunner(application callable, plain presenter,
     TUI route, terminal capability)
  -> ConsoleRunner validates forced TUI eligibility before execution
  -> plain: run_summarize_with_store, then render_summarize_plain
     or
  -> TUI: freeze readable Context catalog, then show shared Context-summary
     workbench
       -> close: return cancellation without application execution
       -> explicit individual Run/Rerun: construct one canonical request
       -> explicit BOTH: construct direct then recursive requests and publish
          only the complete typed pair
       -> for each request call run_summarize_with_store(request, store,
          current snapshot, provider session)
       -> MemoryStoreSummarySourcePort
       -> run_summarize
       -> SummarySourcePort.freeze
            -> existing Context locator / READ Grant projection / frame builder
       -> provider session only for a nonempty frame
            -> existing configured SemanticProvider compatibility connector
            -> summarize_frame prompt, schema, call, and local validation
       -> SummarySourcePort.revalidate
            -> every selected Grant binding, Context identity, and frame digest
       -> SummarizeResult
       -> one result or SummarizeTuiOutcome(direct, recursive)
       -> typed semantic Viewer below the retained controls
```

## Callable matrix

| Callable | Current owner | Intended layer | Inputs/result | External effects | Authority/disclosure | Cache/receipt | Config/secrets | Callers | Evidence | Migration state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `memcommit.application.operations.summarize.application:run_summarize` | Summarize operation application module | Application | `SummarizeRequest` + ports -> `SummarizeResult` | Through injected ports only | Source port freezes READ-authorized evidence before exact lookup or provider session | Optional exact prepared lookup; no durable local result | Receives injected lookup/session; reads no config or secret directly | CLI now; future Python/agent adapters | `tests/test_summarize_application.py` | `VERIFIED` internal boundary |
| `SummarizeRequest` / `SummarizeResult` | Summarize application module | Application contract | Typed request and read-only typed result | None | Carries locator/reach in and public source facts out; no Grant or credential object | Exposes digest/count, not a durable receipt | None | Application and adapters | Direct application tests | `CHARACTERIZED`, internal |
| `SummarySourcePort.freeze` | Protocol in application module; `MemoryStoreSummarySourcePort` implementation | Application port / infrastructure adapter | Request -> frozen `SummaryFrame` + opaque token | Context/Profile/Grant reads in production implementation | Resolves locator and READ before Memory content can reach provider; a recursive local root uses one catalog containing local and READ-granted public names | None | No provider secret | `run_summarize` | CLI, direct production, recursive/direct, mixed local/granted, and granted-projection tests | `VERIFIED` production adapter; shared Grant location deferred |
| `SummarySourcePort.revalidate` | Protocol in application module; `MemoryStoreSummarySourcePort` implementation | Application port / infrastructure adapter | Frozen source -> current frame | Context/Profile/Grant reads | Revalidates every selected granted public-name binding, the selected Context identities, and source digest before result publication | None | None | `run_summarize` | local source-change, mixed-scope Grant revocation, and Grant-revision tests | `VERIFIED` production adapter; shared Grant location deferred |
| `run_summarize_with_store` | Summarize runtime module | Infrastructure/application composition | request + real Store + frozen current name + provider session -> typed result | Real Store/Grant reads, exact Study lookup, and injected provider on miss | Shares the same pre-disclosure and freshness path with CLI and Python runtime | Exact-frame shared Study artifact with compatible cached quality only; no local Summary session | Artifact retains exact provider provenance; lookup requires quality at least equal to the configured request | CLI and `execute_summarize` | Store, CLI, Grant, parity, and exact-prewarm tests | `VERIFIED` internal runtime |
| `execute_summarize` | Summarize runtime module | Internal Python production adapter | request + real Store + provider factory -> typed result | Real Store/Grant reads and provider call on exact miss; no terminal output | Captures current Context once; provider factory is lazy after READ, exact lookup, and nonempty-frame checks | Same Study exact lookup as CLI; no local session | Injected provider factory owns live-call config and secrets | Internal Python caller | real Store, exact hit, provider-free empty frame, no-output, and CLI parity tests | `VERIFIED` internal; not public API |
| `_provider_session` | CLI command adapter | Interface composition | context manager -> provider | Progress rendering and provider connection | Opens only after `run_summarize` observes a nonempty authorized frame | No cache/receipt | Existing provider factory freezes effective selection and secrets | `run_summarize_with_store` through injection | empty/nonempty lifecycle tests and CLI tests | `KEEP`; presentation-specific wrapper |
| `collect_summary_scope` / `collect_summary_frame` | `memcommit.summarize` | Domain evidence projection | authorized lexical roots plus embed policy -> `SummaryFrame` | None | Includes ordinary Memory content only; query-only/ref content excluded; Context UIDs deduplicate lexical and embedded reach | Computes deterministic digest over both traversal axes and sources | None | Source adapter; tests | recursive/direct, lexical descendant, embed, Grant, and semantic policy tests | `KEEP` |
| `summarize_frame` | `memcommit.summarize` | Operation semantic service; finer split deferred | `SummaryFrame` + provider -> `UnderstandingSummary` | One injected provider call for nonempty frame | Sends only frozen aliases, public Context names, and ordinary Memory content | No cache/receipt | Provider already configured by caller | `run_summarize` | schema, unknown-alias, empty, and size-policy tests | `KEEP`; provider call/decoder split not yet justified |
| `SemanticProvider.complete` compatibility connector | provider protocol and existing infrastructure | Infrastructure port and adapters | prompt/schema -> raw completion | Network or subprocess, credentials, timeout | Existing allowlists, endpoint checks, bounds, and error redaction apply | Provider run metadata only; no Summarize receipt | Existing typed config plus secret environment | About 20 command modules; Summarize only changed to injection | Provider command tests and provider rationale | `DEFER`; do not move globally in this slice |
| `UnderstandingSummary` and source-linked parser/schema | shared understanding core | Domain/shared semantic contract | validated text + Memory identities | None | Rejects unknown or unsupported source aliases | None | None | Atomize, Compare, Summarize | `tests/test_summarize.py` and related operation tests | `KEEP` |
| Compare understanding block | `memcommit.adapters.console.commands.compare.presentation:render_comparison` | Compare console projection | `UnderstandingSummary` -> labelled terminal lines | Terminal output only in caller | Escapes presentation; no authority decision | None | None | Compare plain adapter; Summarize deliberately renders the same typed text as its unlabelled artifact body | CLI output tests | `INLINED`; the shared helper was removed after Compare became its only caller, while heading ownership remains operation-specific |
| `ConsoleRunner.run` | `memcommit.adapters.console` | Console route coordinator | typed request + mode -> typed result or interactive cancellation | Plain executes immediately; the injected TUI route controls explicit execution | Forced TUI capability fails before catalog or application execution | None | Injected terminal capability only | Summarize bootstrap | route, cancellation, and command tests | `VERIFIED` for read-only slice |
| `render_summarize_plain` | `memcommit.adapters.console.commands.summarize.presentation` | Plain console presenter | `SummarizeResult` -> terminal output | stdout rendering | No authority or provider decision | None | None | Summarize console runner | exact plain-output tests | `VERIFIED` |
| `project_summarize_result` / `project_summarize_outcome` / `project_summarize_clipboard` / `run_summarize_tui` | `memcommit.adapters.console.commands.summarize.workbench` | Summarize console workbench adapter | frozen readable setup + staged range + injected execute -> one result, complete direct/recursive pair, or cancellation | prompt-toolkit setup/result presentation; individual modes call once and `BOTH` calls direct then recursive; injected plain writer handles `y`/`Y` | Picker never loads Memory content or switches current; every request reauthorizes before provider; copy occurs only from a revalidated typed result; no mutation or partial pair publication | Per-scope Study exact artifacts remain independent; copy creates no structured stage | None | Summarize console runner | projection, dual-view ordering, cancel-before-execute, three-way selection, focused/complete copy, rerun, and PTY evidence | `VERIFIED` |
| `commands.summarize.cmd` | Typer command entry adapter | CLI parsing and error boundary | argv/current CLI state -> exit/output | Deferred Store construction, current snapshot, progress, presentation, and injected plain OS clipboard write | Delegates Store/Grant and semantic sequence to the shared runtime; copy occurs only after result revalidation | No summary receipt; `--copy` and TUI `y`/`Y` create no structured stage | Existing provider bootstrap and platform clipboard adapter | `mem` console entry | CLI/runtime parity, route, copy, and no-eager-execution tests | `MIGRATED` for orchestration and presentation composition |

## Operation matrix

| Operation | Entry points | Application request/result | Authority | Cache/projection | Provider contract | Session/receipt | Review/Apply/CAS | Durable writes | Config | Verification | State |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Summarize | Plain CLI, read-only TUI, internal Store-backed Python production callable; no agent tool | `SummarizeRequest` / `SummarizeResult` | Exact local or granted `READ`; granted binding frozen and revalidated | Study-only exact-frame shared artifact; no projection or composition; cached quality must satisfy the request | Compatible hit or one bounded `summarize_context` call; empty frame provider-free; strict source-linked schema and local validation | Process-local result only; no local Summary session | No review or Apply; source digest is revalidated before return | Shared artifact remains baseline-owned | Exact provider/model/reasoning remain in the artifact key; the current configuration is a minimum quality request | application/runtime parity, recursive/direct/miss/source-change/Grant, and exact-prewarm tests | `VERIFIED` internal application, runtime, and console adapters |

## Provider security matrix

| Operation/call site | Frozen disclosure frame | Pre-connection authority gate | Cache gate | Provider/endpoint policy | Prompt/schema version | Effective budgets | Secret source | Safe provenance/receipt | Failure and no-partial-publication tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Summarize via `summarize_frame` | `SummaryFrame.sources`: temporary alias, public Context name, ordinary Memory content; no `MemoryRef` or `QueryContextRef` content | `SummarySourcePort.freeze` completes locator and READ/Grant projection before exact lookup or provider creation | Exact Study key binds full frame digest, traversal flags, source identities, contract, and cached provider provenance; the shared partial order admits only equal-or-higher compatible quality; empty frame skips both | Existing allowlisted configured adapter; existing loopback/remote endpoint policy | `summarize_context`; source-linked understanding JSON schema; contract version 1 | shared semantic input-character ceiling, response 50,000 characters, understanding text 4,000 characters, configured provider timeout/output allocation | Existing provider adapter environment/secret handling; application sees none | Shared artifact digest; typed result remains process-local | compatible-hit provider prohibition, direct/recursive separation, lower-quality miss, unknown source alias rejection, local source digest change, Grant revision change, and no terminal result on failure |

## Verified compatibility evidence

The focused suite covers:

- TUI/Typer/command-import independence of the application module;
- typed direct invocation and provider-session lifetime;
- real-Store execution without stdout, stderr, Typer, or TUI imports;
- one current-Context snapshot for the Store-backed request;
- forced TUI rejection before Store or provider construction and automatic
  immediate execution for both the command-start current Context and an
  explicit Context operand;
- plain execution followed by its independent presenter, plus TUI cancellation
  before execution, one application call for an individual range, and ordered
  direct/recursive calls for `BOTH`;
- process-local Context selection from the readable Profile catalog and a
  separate `BOTH`/direct/descendants control;
- complete typed dual-result projection and scope-labelled clipboard output;
- focused `y` and complete `Y` TUI copy through the injected plain writer;
- typed Summarize-to-Viewer projection without CLI-output reparsing;
- source resolution failure before provider construction;
- recursive lexical/embed and direct CLI frames;
- plain-text copy success, failure, and no-structured-stage behavior;
- deterministic provider-free empty frames;
- strict rejection of an unknown evidence alias;
- local source change before publication;
- granted READ projection excluding narrower QUERY-only content;
- one recursive public namespace combining local and READ-granted lexical
  descendants while excluding a narrower QUERY-only override;
- identical CLI and Python provider payloads for the granted projection;
- exact Grant revision change and mixed-scope Grant revocation before
  publication; and
- the shared semantic execution policy and provider command boundary;
- direct imports from the new component owners across every migrated consumer;
- real 180×52 color PTY evidence that both `mem summarize` and
  `mem summarize CONTEXT` stay out of the alternate screen while explicit
  `--tui` retains the read-only setup and cancellation boundary;
- real 180×52 color PTY Context-first entry, in-place empty Summary action,
  three-way range transition, complete dual result, focused/complete copy,
  cancellation, read-only byte/checkpoint, and plain-output evidence; and
- an isolated installed-wheel `mem` entry point and component import.

The Context-first dual-result and scoped-copy focused
Summarize/router/component and Grant run passed 90 tests. The preceding
component-extraction baseline migrated TUI consumers
through 1,258 bounded tests; `ruff`, `compileall`, the wheel build, and the
isolated installed entry-point checks passed in that baseline.

The exact commit tree's repository-wide run completed with
`2931 passed, 38 failed, 39 errors` in 233.81 seconds. No Summarize,
console-router, component,
or architecture test failed. Seventy-five failures/errors were Task 2
evaluation cases sharing a frozen discovery-corpus lock mismatch. The two
remaining failures were the pre-existing Atomize grounding capture mismatch and
an authority test that still passes Find's removed `direct` argument.

None enters the Summarize execution path or fails an extracted component
contract. Their stacks point to the named operation and frozen-lock contracts.
They remain baseline work rather than being repaired as part of this
extraction.

## Remaining gates

1. Decide the stable public Python facade only after its store-root ownership,
   default configured-provider bootstrap, error, and lifecycle contracts are
   explicit. Do not export `execute_summarize` as stable merely because it is
   callable.
2. Add a machine-readable adapter and prove CLI/Python result parity without
   parsing terminal output.
3. Select an operation with editable input, review, and a durable-effect
   boundary through the same component and console hierarchy; Summarize's
   Study-only lookup intentionally proves no local session or Apply lifecycle.
4. Continue extracting input, choice, and Context-tree components only as their
   operation slices can migrate every affected consumer and preserve behavior.
5. Revisit shared provider/config bootstrap only after at least two slices show
   the same ownership and failure boundary.

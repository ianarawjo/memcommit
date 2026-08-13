# Summarize application-boundary matrix

## Status

The internal application and production-runtime extractions are implemented and
verified. `run_summarize` completes the use case through abstract ports, while
`execute_summarize` composes it with a real `MemoryStore` and injected provider
without Typer, prompt-toolkit, terminal output, or TUI state. The console host
executes that same path once and presents its typed result through independent
plain and TUI adapters. These are internal boundaries, not yet a stable public
Python API.

Last reviewed: 2026-08-13.

## Objective and non-goals

This slice tests the first architecture seam without changing a measured Study
operation. It extracts only the existing Summarize orchestration:

```text
freeze locator and READ-authorized source
  -> skip provider for an empty frame
  -> otherwise perform one bounded semantic summary
  -> rebuild and revalidate the frozen source
  -> return a typed read-only result
```

It deliberately does not move shared provider implementations or Grant logic,
semantic-execution planning, or understanding models. It does not add a
persistent summary cache, receipt, public client facade, agent tool, editable
TUI state, review, or Apply. Its CLI `--copy` route is a post-result plain-text
presentation effect and creates no structured clipboard stage.

Summarize is also the first complete console-composition slice. The existing
plain route and a new read-only semantic Viewer sit behind an injected console
runner and composition root. Automatic mode uses terminal capability;
`--plain` and `--tui` make the route explicit. The application remains
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
implementation from `memcommit.commands.granted_context`. That module does not
import Typer or prompt-toolkit, but its package location is still a known
reverse dependency. Moving it is deferred until a second vertical slice proves
the same owner and lifecycle; this slice must not copy or partially migrate the
shared Grant rules.

## Current dependency path

```text
Python production caller
  -> execute_summarize(request, store, provider_factory)
  -> run_summarize_with_store
       -> MemoryStoreSummarySourcePort
       -> run_summarize

mem summarize argv
  -> memcommit.commands.summarize.cmd
  -> resolve semantic scope and presentation mode
  -> bootstrap builds ConsoleRunner(application callable, plain presenter,
     TUI presenter, terminal capability)
  -> ConsoleRunner validates forced TUI eligibility before execution
  -> run_summarize_with_store(request, store, current snapshot, provider session)
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
  -> exactly one presenter
       -> render_summarize_plain
       or
       -> project_summarize_result -> shared semantic Viewer
```

## Callable matrix

| Callable | Current owner | Intended layer | Inputs/result | External effects | Authority/disclosure | Cache/receipt | Config/secrets | Callers | Evidence | Migration state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `memcommit.summarize_application:run_summarize` | Summarize application module | Application | `SummarizeRequest` + ports -> `SummarizeResult` | Through injected ports only | Source port must freeze READ-authorized evidence before provider session opens | No summary cache or receipt | Receives a provider session; reads no config or secret directly | CLI now; future Python/agent adapters | `tests/test_summarize_application.py` | `VERIFIED` internal boundary |
| `SummarizeRequest` / `SummarizeResult` | Summarize application module | Application contract | Typed request and read-only typed result | None | Carries locator/reach in and public source facts out; no Grant or credential object | Exposes digest/count, not a durable receipt | None | Application and adapters | Direct application tests | `CHARACTERIZED`, internal |
| `SummarySourcePort.freeze` | Protocol in application module; `MemoryStoreSummarySourcePort` implementation | Application port / infrastructure adapter | Request -> frozen `SummaryFrame` + opaque token | Context/Profile/Grant reads in production implementation | Resolves locator and READ before Memory content can reach provider; a recursive local root uses one catalog containing local and READ-granted public names | None | No provider secret | `run_summarize` | CLI, direct production, recursive/direct, mixed local/granted, and granted-projection tests | `VERIFIED` production adapter; shared Grant location deferred |
| `SummarySourcePort.revalidate` | Protocol in application module; `MemoryStoreSummarySourcePort` implementation | Application port / infrastructure adapter | Frozen source -> current frame | Context/Profile/Grant reads | Revalidates every selected granted public-name binding, the selected Context identities, and source digest before result publication | None | None | `run_summarize` | local source-change, mixed-scope Grant revocation, and Grant-revision tests | `VERIFIED` production adapter; shared Grant location deferred |
| `run_summarize_with_store` | Summarize runtime module | Infrastructure/application composition | request + real Store + frozen current name + provider session -> typed result | Real Store/Grant reads and injected provider | Shares the same pre-disclosure and freshness path with CLI and Python runtime | No cache/receipt | Does not load config or secrets itself | CLI and `execute_summarize` | Store, CLI, Grant, and parity tests | `VERIFIED` internal runtime |
| `execute_summarize` | Summarize runtime module | Internal Python production adapter | request + real Store + provider factory -> typed result | Real Store/Grant reads and provider call; no terminal output | Captures current Context once; provider factory is lazy after READ and nonempty-frame checks | No cache/receipt | Injected provider factory owns config and secrets | Internal Python caller | real Store, provider-free empty frame, no-output, and CLI parity tests | `VERIFIED` internal; not public API |
| `_provider_session` | CLI command adapter | Interface composition | context manager -> provider | Progress rendering and provider connection | Opens only after `run_summarize` observes a nonempty authorized frame | No cache/receipt | Existing provider factory freezes effective selection and secrets | `run_summarize_with_store` through injection | empty/nonempty lifecycle tests and CLI tests | `KEEP`; presentation-specific wrapper |
| `collect_summary_scope` / `collect_summary_frame` | `memcommit.summarize` | Domain evidence projection | authorized lexical roots plus embed policy -> `SummaryFrame` | None | Includes ordinary Memory content only; query-only/ref content excluded; Context UIDs deduplicate lexical and embedded reach | Computes deterministic digest over both traversal axes and sources | None | Source adapter; tests | recursive/direct, lexical descendant, embed, Grant, and semantic policy tests | `KEEP` |
| `summarize_frame` | `memcommit.summarize` | Operation semantic service; finer split deferred | `SummaryFrame` + provider -> `UnderstandingSummary` | One injected provider call for nonempty frame | Sends only frozen aliases, public Context names, and ordinary Memory content | No cache/receipt | Provider already configured by caller | `run_summarize` | schema, unknown-alias, empty, and size-policy tests | `KEEP`; provider call/decoder split not yet justified |
| `SemanticProvider.complete` compatibility connector | provider protocol and existing infrastructure | Infrastructure port and adapters | prompt/schema -> raw completion | Network or subprocess, credentials, timeout | Existing allowlists, endpoint checks, bounds, and error redaction apply | Provider run metadata only; no Summarize receipt | Existing typed config plus secret environment | About 20 command modules; Summarize only changed to injection | Provider command tests and provider rationale | `DEFER`; do not move globally in this slice |
| `UnderstandingSummary` and source-linked parser/schema | shared understanding core | Domain/shared semantic contract | validated text + Memory identities | None | Rejects unknown or unsupported source aliases | None | None | Atomize, Compare, Summarize | `tests/test_summarize.py` and related operation tests | `KEEP` |
| `understanding_lines` | `memcommit.interfaces.understanding` | Shared interface projection | `UnderstandingSummary` -> terminal lines | Terminal output only in caller | Escapes presentation; no authority decision | None | None | Compare and Summarize plain adapters | CLI output tests | `MIGRATED` from command ownership |
| `ConsoleRunner.run` | `memcommit.interfaces.console` | Console route coordinator | typed request + mode -> typed result | Chooses one injected presenter after one application execution | Forced TUI capability fails before application execution | None | Injected terminal capability only | Summarize bootstrap | router and command tests | `VERIFIED` for read-only slice |
| `render_summarize_plain` | `memcommit.interfaces.cli.summarize` | Plain CLI presenter | `SummarizeResult` -> terminal output | stdout rendering | No authority or provider decision | None | None | Summarize console runner | exact plain-output tests | `VERIFIED` |
| `project_summarize_result` / `run_summarize_tui` | `memcommit.interfaces.tui.operations.summarize` | TUI operation adapter | `SummarizeResult` -> typed Viewer document / read-only interaction | prompt-toolkit presentation only | Does not reopen sources, call provider, or mutate | None | None | Summarize console runner | projection, pipe-input, architecture, and PTY evidence | `VERIFIED` |
| `commands.summarize.cmd` | Typer command entry adapter | CLI parsing and error boundary | argv/current CLI state -> exit/output | Deferred Store construction, current snapshot, progress, presentation, optional plain OS clipboard write | Delegates Store/Grant and semantic sequence to the shared runtime; copy occurs only after result revalidation | No summary receipt; `--copy` creates no structured stage | Existing provider bootstrap and platform clipboard adapter | `mem` console entry | CLI/runtime parity, route, copy, and no-eager-execution tests | `MIGRATED` for orchestration and presentation composition |

## Operation matrix

| Operation | Entry points | Application request/result | Authority | Cache/projection | Provider contract | Session/receipt | Review/Apply/CAS | Durable writes | Config | Verification | State |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Summarize | Plain CLI, read-only TUI, internal Store-backed Python production callable; no agent tool | `SummarizeRequest` / `SummarizeResult` | Exact local or granted `READ`; granted binding frozen and revalidated | No result cache; granted readable projection only | One bounded `summarize_context` call; empty frame provider-free; strict source-linked schema and local validation | Process-local result only | No review or Apply; source digest is revalidated before return | None | Injected or existing configured provider snapshot; no Summarize-owned keys | application/runtime parity, route/component/architecture tests, recursive/direct/empty/invalid-output/source-change/Grant tests, PTY and installed-wheel evidence | `VERIFIED` internal application, runtime, and console adapters |

## Provider security matrix

| Operation/call site | Frozen disclosure frame | Pre-connection authority gate | Cache gate | Provider/endpoint policy | Prompt/schema version | Effective budgets | Secret source | Safe provenance/receipt | Failure and no-partial-publication tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Summarize via `summarize_frame` | `SummaryFrame.sources`: temporary alias, public Context name, ordinary Memory content; no `MemoryRef` or `QueryContextRef` content | `SummarySourcePort.freeze` completes locator and READ/Grant projection before provider session creation | No cache; empty frame deterministically skips provider | Existing allowlisted configured adapter; existing loopback/remote endpoint policy | `summarize_context`; source-linked understanding JSON schema; current contract is code-owned but not separately versioned in a receipt | shared semantic input-character ceiling, response 50,000 characters, understanding text 4,000 characters, configured provider timeout/output allocation | Existing provider adapter environment/secret handling; application sees none | Process-local provider run metadata only; no durable Summarize receipt | empty-provider prohibition, unknown source alias rejection, oversized planning policy, local source digest change, Grant revision change, and no terminal result on CLI failure |

## Verified compatibility evidence

The focused suite covers:

- TUI/Typer/command-import independence of the application module;
- typed direct invocation and provider-session lifetime;
- real-Store execution without stdout, stderr, Typer, or TUI imports;
- one current-Context snapshot for the Store-backed request;
- forced TUI rejection before Store or provider construction and automatic
  TTY/plain route selection;
- one application execution followed by exactly one independent presenter;
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
- real 180×52 color PTY entry, focus, close, and plain-output evidence; and
- an isolated installed-wheel `mem` entry point and component import.

The exact commit tree's focused Summarize/router/component and Grant run passed
93 tests. The migrated
TUI consumers passed 1,258 tests across bounded partitions. `ruff`, `compileall`,
the wheel build, and the isolated installed entry-point checks also passed.

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
3. Select a second non-Study operation to test editable input, review, and a
   cache, receipt, or durable-effect boundary through the same component and
   console hierarchy; Summarize proves none of those.
4. Continue extracting input, choice, and Context-tree components only as their
   operation slices can migrate every affected consumer and preserve behavior.
5. Revisit shared provider/config bootstrap only after at least two slices show
   the same ownership and failure boundary.

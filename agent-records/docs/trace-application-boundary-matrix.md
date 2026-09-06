# Trace application boundary matrix

## Closure statement

Every currently implemented Trace route enters one terminal-independent
application/runtime boundary. Trace freezes one exact Context, Memory,
MemoryRef, or READ-granted current-Memory subject, validates the returned
report against that durable identity, and performs no provider or Context
mutation lifecycle. Missing future Python or agent adapters do not broaden the
current CLI route set.

| Route | Entry | Application path | Result | Effect | Evidence |
| --- | --- | --- | --- | --- | --- |
| Explicit Context | `mem trace CONTEXT`, `mem trace --context CONTEXT` | CLI syntax classification → exact `TraceContextTarget` → `execute_trace` | `ContextHistorySlice` | None | Context Trace and application runtime tests |
| Explicit current or historical Memory | `mem trace UID`, `mem trace CONTEXT:UID` | `TraceMemoryTarget` → readable/current resolution with retained-local fallback → `execute_trace` | `MemoryHistory` | None | Trace/Rationale, compact output, and application tests |
| Explicit MemoryRef | same direct-item forms | exact local relationship occurrence resolution → `execute_trace` | `MemoryReferenceTraceReport` with independent target status/Trace | None | typed Trace/Rationale and Reference tests |
| READ-granted current Memory | qualified or unique Profile-readable UID | exact active Grant resolution → current-only freeze → `execute_trace` | `GrantedMemoryTraceReport` with visible access route and hidden owner history | None | authority-Grant and application dispatch tests |
| Interactive target selection | `mem trace` in a TTY | `TraceTargetCatalogRequest` → `load_trace_target_catalog` → Switch-style Context/Memory tree → exact `TraceContextTarget` or `TraceMemoryTarget` → `execute_trace` | Same Context or Memory result | None | picker ownership and application catalog tests |
| JSON | explicit target plus `--json` | same execution boundary | `TraceResult.to_dict()`/typed report JSON | stdout only | chronological JSON regression |
| Interactive Context or direct-Memory report | complete `mem trace` request in a TTY | same complete application result | existing single read-only Viewer over the bounded fragment document | terminal presentation only | Viewer routing and compact projection tests |
| Bounded or complete text | `--limit N`, `--all`, `--verbose` through a pipe/non-TTY; `mem log --memory` for local Memory lineage | same complete application result | adapter-only bounded/plain projection | stdout only | Viewer routing and compact projection tests |

## Callable matrix

| Callable | Current owner | Responsibility | Inputs/result | Boundary |
| --- | --- | --- | --- | --- |
| `list_trace_targets` | `memcommit.application.operations.trace.application` | Validate one operation-owned selection catalog request/result | `TraceTargetCatalogRequest` + `TraceSourcePort` → `TraceTargetCatalog` | No Store or terminal import |
| `run_trace` | same | Freeze, reconstruct, and validate one exact Trace subject | `TraceRequest` + `TraceSourcePort` → `TraceResult` | Report type and Context/Memory identity must match the frozen subject |
| `MemoryStoreTraceSource.target_catalog` | `memcommit.application.operations.trace.runtime` | Resolve local History authority and build direct-Memory candidates | typed catalog request → frozen catalog | READ plus retained-owner Trace boundary before checkpoint inspection |
| `MemoryStoreTraceSource.freeze` | same | Resolve Context/Memory grammar semantics, readable ambiguity, relationship kind, and Grant route | typed request → `FrozenTraceSubject` | Exact command-start current Context and current authority |
| `MemoryStoreTraceSource.reconstruct` | same | Delegate verified history reconstruction for the already frozen subject kind | frozen subject → one typed report variant | No terminal or provider effects |
| `reconstruct_history_graph` | `memcommit.application.capabilities.history.reconstruction.history_graph_reconstruction` | Normalize verified Context, Memory, and MemoryRef evidence into one operation/occurrence topology | History evidence source + exact owned Context → `HistoryGraphAssembly` | Description/content are payload; typed identities and relations alone define connectivity |
| `HistoryGraph` | `memcommit.application.capabilities.history.model.topology` | Own operation nodes, checkpoint/current steps, occurrence nodes, typed relations, UID-component traversal, and operation counting | immutable topology → deterministic graph queries | Grant is not a hierarchy/ancestry edge; relationship targets are not direct-Memory selectors |
| `derive_memory_history_events` | `memcommit.application.capabilities.history.reconstruction.memory_history_reconstruction` | Interpret verified checkpoints and receipts as deterministic Memory events | exact local Context → events, warnings, verified frames | Shared History stage; no target selection or presentation |
| `reconstruct_memory_history` | `memcommit.application.capabilities.history.query.memory_history_slicing` | Select a graph UID occurrence and project its typed connected component | History evidence source + owner Context + selector → `MemoryHistory` | Trace, Rationale, and Reference may consume the same History semantics |
| `build_context_history_slice` | `memcommit.application.capabilities.history.query.context_history_slicing` | Project ordered root-Context operation steps from the shared topology | History evidence source + exact Context → `ContextHistorySlice` | Checkpoints with no direct Memory delta remain visible |
| `build_reference_trace` | `memcommit.application.operations.trace.reference_lineage` | Project one relationship occurrence and independently authorize its target lineage | Store + owner Context + selector → `MemoryReferenceTraceReport` | Live Embed and snapshot Reference remain typed graph edges; occurrence and target identity stay separate |
| `build_granted_memory_trace` | `memcommit.application.operations.trace.granted_view` | Freeze the current readable Memory and exact Grant route while keeping owner history hidden | granted access + selector → `GrantedMemoryTraceReport` | READ is not checkpoint authority |
| `execute_trace` | same | Store-backed composition of `run_trace` | request + explicit Store → result | No terminal output |
| `commands.trace.cmd` | console adapter | Parse CLI syntax/options, launch the direct Context/Memory browser, render result, and translate errors | argv/TUI → request + presentation | No direct authority resolution or report-builder call |

## Invariants

1. A command-start current Context name is captured once and accompanies every
   relative locator and omitted owner through the application request.
2. Existing Context names win the ambiguous positional CLI grammar before a
   typed request is constructed. This is syntax translation only; authority
   and reconstruction remain operation-owned.
3. A bare Memory UID searches the frozen current Profile-readable ordinary
   Memory namespace without preferring current or local ownership. Local
   retained Memories and MemoryRefs are fallback candidates only when no
   current readable ordinary Memory matches.
4. Interactive catalog rows are local Contexts and direct Memory candidates.
   Historical UIDs use retained evidence. The frozen descendant tree is browse
   breadth only: Enter always returns one exact Context or Memory target.
5. `FrozenTraceSubject` preserves the exact subject kind, Context UID/public
   name, and selected UID. A mismatched report is rejected before presentation.
6. MemoryRef occurrence history and target Memory lineage remain separate.
   Snapshot targets are fixed; unavailable live targets remain an explicit
   limit.
7. READ-granted current content never implies authority checkpoint access.
   The current Grant route remains visible while history is marked hidden.
8. Presentation bounds do not truncate the application result or JSON. Trace
   performs no provider call, Context mutation, checkpoint, cache, saved
   analysis, or current-pointer change.
9. Operation identity uses verified command-operation/operation UID when
   available and exact Context/checkpoint identity otherwise. Human-readable
   descriptions never determine a node or edge.
10. The same Memory UID may have several state-anchored occurrences. Only
    typed lineage-producing effects broaden a selected Memory component;
    Embed, Reference, Grant, and lexical hierarchy do not.

## Internal normal form

All four report classes and the Context, Memory, and MemoryRef construction
stages have one physical owner under Trace. Their public representations remain
purpose-specific, but they are projections of one operation/occurrence
topology. READ-granted current Trace remains an authority-limited view rather
than a hidden checkpoint projection.

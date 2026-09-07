# Trace application boundary design rationale

## Motivation

Trace entered the prototype as a console command over a root-level provenance
module. Later ownership relocations grouped checkpoint verification and lineage
reconstruction under retained history because Log, Trace, Rationale, Reference,
restoration, and mutation verification all touched parts of that code. They did
not distinguish shared retained evidence from the Trace-specific interpretation
reused by those callers, or extract the Trace use case into
`application.operations.trace`.

As a result, the console command itself selected among Context, Memory,
MemoryRef, and granted-current reports; resolved READ and retained-history
authority; opened retained records; called four independent report builders;
and only then chose a renderer. Checkpoint and receipt verification was shared,
but Memory event derivation, UID-component construction, and the four observable
lineage variants were Trace semantics without a terminal-independent owner.

## Decision

`memcommit.application.operations.trace` owns the Trace use case. Its boundary
has two entry contracts:

1. `list_trace_targets` accepts a typed local Context-range request and returns
   a frozen catalog of direct current or historical Memory candidates. It
   contains no terminal selection state.
2. `run_trace` accepts either a typed Context target or a typed Memory target,
   freezes and authorizes the exact subject through a port, reconstructs its
   report, and validates that the report kind and durable Context/Memory
   identities match the frozen subject.

The Store-backed composition lives in `trace.runtime`. It resolves existing
Context locators against the command-start current Context, preserves the
Profile-wide ambiguity contract for bare Memory UIDs, distinguishes ordinary
Memory, MemoryRef, and READ-granted current views, enforces the retained-owner
history boundary, and delegates to History-owned Context/Memory queries and
Trace-owned MemoryRef/granted-current projections. Those constructors consume
verified retained records without giving target or result policy back to
persistence or the console.

The console Trace command retains only interface concerns: CLI grammar,
content-free Recents, interactive target choice, option validation, terminal
error translation, JSON/plain presentation, and completed-attempt annotation.
Neither the application contract nor its runtime imports Typer,
prompt-toolkit, or a console module.

## Request and result contract

```text
TraceTargetCatalogRequest
  -> TraceSourcePort.target_catalog
  -> TraceTargetCatalog
  -> console picker chooses an exact owner + UID

TraceRequest
  target = TraceContextTarget | TraceMemoryTarget
  + command-start current Context snapshot
  -> TraceSourcePort.freeze
  -> FrozenTraceSubject
  -> TraceSourcePort.reconstruct
  -> TraceResult
```

`FrozenTraceSubject.kind` is one of `CONTEXT`, `MEMORY`,
`MEMORY_REFERENCE`, or `GRANTED_MEMORY`. The application rejects a report whose
type, Context UID/name, or selected UID differs from that frozen identity. A
presentation limit, verbose flag, JSON selection, focus position, or terminal
document is not part of the application request or result.

## History and Trace boundary

Canonical History is the shared evidence capability. It owns checkpoint
flattening, snapshot normalization, operation-record correlation, Memory
effect derivation, Reference occurrence derivation, and the common graph.
Trace owns subject selection, authority checks, and the Context, Memory,
MemoryRef, or granted-current result union. Rationale consumes History slices
directly instead of depending on Trace as an accidental data service.

Context, Memory, and MemoryRef projections now share the operation/occurrence
normal form described in
`trace-lineage-normal-form-design-rationale.md`. Context follows ordered
operation evidence steps; Memory follows typed relations from the selected UID
occurrence; MemoryRef keeps its relationship occurrence distinct from its
target. History verification remains below this topology and does not acquire
Trace target, report, or presentation policy.

## Direct imports and the application export boundary

`trace.application` previously advertised 30 names, including 13 imported
History values/builders and Trace report projections. That made shared Memory
targeting, Log coordination, and the Rationale console depend on the Trace
application module merely to obtain functions owned elsewhere.

Consumers now import History queries from their owning query modules and
Trace report projections from `trace.granted_view` or
`trace.reference_lineage`. `trace.application.__all__` contains only its 17
locally defined request, catalog, subject, result, error, port, and execution
names. The four concrete report types remain internal imports because the
result union and frozen-subject validation use them. Imports used only for
forwarding have been removed.

Removing names from `__all__` alone would leave explicit imports unchanged,
so this change also migrates production and test consumers to the direct
owners. It preserves the same class/function objects, request validation,
authority checks, report serialization, and CLI/TUI behavior. No compatibility
forwarder is added for these internal import paths; downstream code using the
removed forwarding imports must adopt the owning module.

The remaining 17 names stay together for this change. They comprise twelve
request/result/catalog data types or aliases, two errors, one source port,
and two entry functions. Further restructuring should first examine whether
each distinction is necessary or duplicates another contract. Export count
alone does not justify a file split; related request and result types can be
easier to understand together. Separating data contracts from execution is an
option only if it improves that understanding.

## Authority and relationship boundaries

- A locally owned Context or Memory may expose its retained checkpoints after
  the existing Trace-access check.
- A READ-granted Memory currently returns the existing typed current view and
  Grant route. READ still does not expose authority checkpoints.
- A MemoryRef remains a relationship occurrence with an independently
  authorized target Trace. The Trace operation selects this result variant but
  does not collapse pointer occurrence history into target Memory identity.
- Interactive target listing remains direct-Memory-only, matching the current
  product contract. Explicit selectors can still identify a MemoryRef.

## Compatibility and limitations

This slice changes ownership and Trace's internal normal form, not persisted
evidence or output. `ContextHistorySlice` and `MemoryHistory` are History query
values; `MemoryReferenceTraceReport` and `GrantedMemoryTraceReport` remain
Trace-owned authority projections. Together they form the Trace result union.
The former retained-history package has no compatibility facade; production
code imports the narrow History or Trace owner directly.

The console still classifies the ambiguous positional CLI spelling as Context
versus Memory before constructing a typed request. That is syntax translation,
not authority or reconstruction. Every selected or explicit target enters the
same operation execution boundary before a report is returned.

The focused boundary matrix reviews every current CLI route through the typed
catalog and execution contracts, so Trace is classified `CLOSED` for its
current route set. The common-lineage migration remains internal to that closed
boundary; it does not require target resolution or authority to return to the
console adapter.

# Public client operation assembly

Last reviewed: 2026-08-15.

## Problem

`IMPORT-01` stopped the public client from eagerly loading every operation,
but its implementation still kept request construction, Store/Profile
selection, authority checks, runtime calls, error projection, and public DTO
projection in one `api/client.py` module. Lazy loader functions prevented
premature imports without assigning a physical owner to that composition.

That was an effective import gate but only a transitional assembly boundary.
It left the facade large, made operation-specific test injection appear to be
client state, and allowed a later edit to reconnect unrelated operations in
the same file.

## Selected structure

The stable `MemCommitClient` remains the public facade. It owns one immutable
internal `ClientRuntime` snapshot containing its Store, resolved Profile and
Store root, query configuration, and provider factories. Each public method
imports one private operation adapter and passes that snapshot plus the public
arguments:

```text
api/client.py
  -> api/_runtime.py
  -> api/_operations/<operation>.py
       -> application/runtime
       -> public DTO and error projection
```

Operation adapters must not import or retain `MemCommitClient`. The dependency
points inward from the facade through the internal runtime value. Shared error
and provider projection belongs under `api/_support`; operation meaning,
authority, request validation, and result projection remain in the operation
adapter rather than a generic engine.

Ground-specific paths remain separate adapters. A standalone Distill or
Elaborate adapter must not import its Ground adapter; the Ground adapter may
depend inward on the same standalone application/runtime.

## Migration and compatibility

Extraction proceeds one already-tested public operation at a time. Add is the
first proof because it exercises ordered input, local and CREATE-granted
targets, relative Context resolution, one checkpoint, and the public error
taxonomy without a semantic provider. Its public method signature, result
types, authority ordering, and durable effect remain unchanged.

Query is the second proof and moves all three independently authorized routes
together: ordinary readable-Context answers, QUERY-granted reads plus optional
session publication, and legacy `QueryContextRef` routing. Their shared public
operation adapter owns provider-failure projection while preserving the
separate application/runtime requests, authority boundaries, and publication
semantics. Default provider connectors are now lazy support functions captured
in `ClientRuntime`, rather than bound methods that retain the facade.

The former module-global `api.client.run_add` test seam is intentionally moved
to `api._operations.add.run_add`, the module that now owns Add assembly. This
is a private test/injection path, not a public API spelling. The operation
module remains patchable without reintroducing client-owned implementation
symbols.

Meld is the final operation in the committed public facade to move. Its whole
durable lifecycle moves together so start, restart, follow-up, preserve,
defer, and apply cannot acquire different dependency snapshots. With that
move, the loader namespace and its sentinels are removed from `client.py`.
Typer command registration remains a separate console composition boundary.

The move also closes one accidental taxonomy leak: reading the current
Context for a Meld formerly reused a client helper that raised
`QueryStorageError`. The Meld adapter now projects that failure as
`MeldStorageError`, matching every other Meld storage failure.

## Invariants

1. Importing or constructing the client imports `ClientRuntime` and bounded
   public values, but no private operation adapter or application runtime.
2. Calling one public method imports only its operation adapter and transitive
   dependencies shared or owned by that operation.
3. An operation adapter never imports the client facade or another sibling
   operation adapter.
4. The immutable runtime snapshot uses the exact Store/Profile/provider values
   frozen by the client constructor; it does not resolve global state again
   except where the operation already requires active-Profile revalidation.
5. Public input, result, error, authority, provider, checkpoint, and mutation
   behavior remains identical across extraction.
6. Fresh-process and installed-wheel tests verify the physical import graph;
   ordinary in-process tests verify behavioral parity.

## Verification

The extracted surface passed 113 focused tests on the latest Meld runtime,
covering Add, all Query routes, the public Meld lifecycle, agent adapters,
fresh-process import isolation, Store-root handling, and the agent registry.
The agent/MCP projection suite passed 76 tests after its stale two-tool
expectation was updated to include the already registered Meld tool.

An isolated `uv build` wheel was installed with the `mcp` extra under Python
3.13. From that `site-packages` origin, constructing the client loaded no
operation adapter; selecting Add, Query, and Meld loaded only the requested
adapter in sequence. The installed `mem-mcp` stdio entry point initialized,
listed Query, Add, and Meld, applied one two-Memory Add with exactly one
checkpoint, and returned the typed unknown-tool error.

The same installed wheel's general `mem --help` entry point remains blocked by
an independent repository-state mismatch: `quality_audit` imports
`QualityFindSourceFrame`, while that definition is not yet present in the
committed `quality_find_workbench`. The working tree contains the pending
quality-find implementation, but it was intentionally not absorbed into this
assembly-boundary change. Therefore this verification proves the Python and
MCP distribution boundaries, not full CLI readiness.

## Remaining rollout

Add, Query, and the complete Meld lifecycle are now extracted; the committed
public facade contains delegation and shared runtime construction only. Fit,
Elaborate, standalone Distill, and their Ground adapters must enter through
the same boundary when those public methods are published. Audit the CLI
registry independently afterward.

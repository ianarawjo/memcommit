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

Meld is the final operation in the original public facade to move. Its whole
durable lifecycle moves together so start, restart, follow-up, preserve,
defer, and apply cannot acquire different dependency snapshots. With that
move, the loader namespace and its sentinels are removed from `client.py`.
Typer command registration remains a separate console composition boundary.

Atomize Grounding is built directly in the extracted shape. Its five public
lifecycle methods delegate to one operation-owned assembly and reuse the same
application/runtime port as the CLI. The adapter deliberately requires an
existing saved Atomize analysis/workbench rather than hiding a second semantic
operation inside Grounding Start.

Fit, Distill, and Elaborate follow the same boundary. The client exposes only
typed inputs, proposals, results, and stable public errors; private operation
adapters own request construction, provider projection, and application/runtime
calls. Standalone Distill and Elaborate keep their Ground imports inside the
Ground-selected method, so importing or calling the standalone route does not
assemble the Ground subsystem. Distill Apply accepts the exact opaque proposal
returned by the same client surface and revalidates its frozen Source before
publishing one new Context.

The Meld move also closes one accidental taxonomy leak: reading the current
Context formerly reused a client helper that raised `QueryStorageError`. The
Meld adapter projects that failure as `MeldStorageError`, matching every other
Meld storage failure.

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

Fresh-process tests construct the client with no operation assembly loaded,
then select Add, Query, Meld, and standalone semantic routes independently.
They also import every private adapter while blocking any dependency back on
the client facade. Behavioral tests cover typed Fit judgments, standalone and
Ground Distill/Elaborate proposals, exact Distill Apply, stable error mapping,
and agent/MCP projections.

## Remaining rollout

Add, Query, the complete Meld lifecycle, Atomize Grounding, Fit, Distill, and
Elaborate now have operation-owned assemblies. The public client contains only
stable construction, typed signatures, and local delegation imports. Future
public operations must enter through the same boundary; CLI registration and
installed-wheel verification remain independent rollout concerns.

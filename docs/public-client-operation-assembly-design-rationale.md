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

Structural Atomize follows as a separate sibling adapter. Its open method
delegates to the saved/prepared/provider analysis boundary and freezes the
complete durable pair as an opaque proposal revision. Its public mutation is
named `apply_atomize_as_is` because the slice does not edit responses or expose
Save As. A different durable Output plan is visible in the result but blocks
the in-place call, so public composition cannot silently reinterpret TUI review
state.

The Meld move also closes one accidental taxonomy leak: reading the current
Context formerly reused a client helper that raised `QueryStorageError`. The
Meld adapter projects that failure as `MeldStorageError`, matching every other
Meld storage failure.

Fit, Distill, and Elaborate follow the same boundary without being collapsed
into one generic semantic operation. Fit owns a proposition-only, Store-free
adapter. Standalone Distill owns Context freezing and exact reviewed Apply;
Ground Distill owns the separately frozen Ground revision and cannot Apply.
Standalone Elaborate owns explicit Goal-or-Rules input, while Ground Elaborate
owns its exact Ground Goal-or-active-Rules projection. The standalone adapters
never import either Ground adapter.

The two Distill routes and two Elaborate routes share only bounded provider
failure handling and public DTO projection under `api/_support/semantic.py`.
They do not import sibling operation adapters, infer Ground state, or share
mutation authority. This keeps their common application meaning reusable
without making the client facade or a generic semantic dispatcher their owner.

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

The prior extracted surface passed 194 focused tests after the Atomize
Grounding and shared-interface changes were integrated. The structural
Atomize rollout then passed 284 focused regressions with one skipped platform
case. Together the sets cover the QualityFind
source frame, Distill and Elaborate core/CLI/TUI behavior, Add, every Query
route, the complete Meld and Atomize Grounding public lifecycles, structural
Atomize open and exact-version Apply, all eight agent adapters, MCP projection,
and fresh-process import isolation. Ruff passed for
every Python file changed by this rollout, the package compiled, and
`python -m memcommit.cli --help` loaded the Fit, Distill, and Elaborate commands.

An isolated `uv build` wheel was installed with the `mcp` extra under Python
3.13. From that `site-packages` origin, constructing the client loaded no
operation adapter. An invalid standalone Elaborate request then loaded only
`api._operations.elaborate`, not Ground Elaborate or Distill. The installed
Ground Distill route loaded only `api._operations.ground_distill`, not the
standalone Distill or Ground Elaborate adapter. The installed
`mem` entry point listed Fit, Distill, and Elaborate. The installed `mem-mcp`
stdio entry point initialized and listed Query, Add, Meld, structural Atomize,
Atomize Grounding, Distill, Elaborate, and Fit. It opened one saved Grounding
session, applied one two-Memory Add with exactly one checkpoint, ran a saved
structural Atomize open/Apply/retry with one checkpoint, and returned the typed
unknown-tool error.

The earlier general `mem --help` blocker was a partial-commit mismatch between
`quality_audit` and `QualityFindSourceFrame`. The committed aggregate
source-frame implementation and owner-aware finder payload now pass their
focused tests and the installed CLI gate.

## Remaining rollout

Add, Query, the complete Meld lifecycle, structural Atomize analysis/in-place
Apply, Atomize Grounding, Fit, standalone Distill, Ground Distill, standalone
Elaborate, and Ground Elaborate are now operation-owned assemblies. Their
public facade methods contain delegation and shared runtime construction only.
New public operations must add a sibling adapter and fresh-process import
contract rather than restoring client-owned loaders or assembly. The CLI and
agent registries remain independently composed and tested boundaries rather
than client-owned assembly.

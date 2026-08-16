# Structural Atomize public Python API

Last reviewed: 2026-08-15.

## Problem

Structural Atomize already had interface-independent analysis-open and in-place
Apply use cases, but a Python caller still had to import internal session,
workbench, Store, prewarm, and checkpoint types. Reconstructing those steps in
another adapter would risk a different cache policy, a forged Apply revision,
or a mutation against a workbench that changed after review.

The public boundary therefore needs to expose useful analysis and lineage while
retaining the exact saved analysis/workbench pair as an opaque application
revision.

## Selected contract

`MemCommitClient` exposes two structural methods:

```python
proposal = client.open_atomize_analysis(
    context_name=None,
    refresh=False,
    use_prepared=True,
)
receipt = client.apply_atomize_as_is(proposal)
```

`open_atomize_analysis` resolves an explicit or current local Context once and
delegates to the existing analysis runtime. Its `origin` is exactly one of:

- `SAVED`: the current durable analysis/workbench pair was reused without a
  provider connection;
- `EXACT_PREWARM`: a declared hidden Study artifact matched and was first
  materialized as the ordinary durable pair, also without a provider; or
- `PROVIDER`: one new complete analysis was produced and saved.

`refresh=True` is an explicit provider request and therefore dominates the
general `use_prepared` preference. `use_prepared=False` disables only hidden
prewarm lookup; it does not disable exact saved-session reuse. That distinction
matches the existing operation rather than turning one cache preference into a
new refresh spelling.

The immutable public proposal includes the overview, every direct-Memory
classification, proposed split children and evidence spans, review findings,
the durable Output plan, and an opaque version. It privately retains the typed
`AtomizeSessionSnapshot`; Apply never reconstructs acceptance from public IDs or
digests.

`apply_atomize_as_is` means exactly the existing local in-place final action:

- `COMPOSITE` sources split; `ATOMIC`, `UNCERTAIN`, and
  `NON_PROPOSITIONAL` sources preserve their identity and content;
- open optional findings remain open and are audited as `AS_IS`, never
  fabricated into answers;
- an all-preserved result still records one deliberate Atomize checkpoint and
  terminal receipt;
- the Source, analysis, and complete workbench revision are rechecked before
  mutation; and
- an exact retry adopts only the terminal application receipt added to the
  accepted workbench, recovers the same checkpoint, and creates no second
  effect. Any other workbench edit remains a conflict.

## Save As boundary

This slice does not publish the internal structural Save As lifecycle. A saved
workbench can already contain a different Output plan, so the proposal exposes
`output_context_name` and `in_place_apply_allowed`. The public in-place method
rejects such a proposal before mutation instead of silently changing the plan
or applying to the Source.

Save As requires a separately reviewed public contract for require-new
authority, destination collision and partial-publication recovery. Workbench
response editing and compound incorporate-and-apply are also outside this
slice. They remain available through the reviewed CLI/TUI lifecycle.

## Error and dependency boundary

Structural Atomize has its own public taxonomy rather than reusing
conversational `AtomizeGrounding*` failures:

- `AtomizeInputError` for invalid public arguments or an ineligible Output
  plan;
- `AtomizeContextError` for a missing local Context;
- `AtomizeProviderFailure` for endpoint construction or transport failure;
- `AtomizeConflictError` for stale Source or changed accepted session state;
- `AtomizeStorageError` for local I/O failure; and
- `AtomizeExecutionError` for invalid semantic output or another complete
  operation failure.

The client facade lazily imports `api._operations.atomize`. Constructing a
client or importing its DTOs does not load structural analysis/application
runtimes. The operation adapter receives `ClientRuntime` and never imports the
client facade, command modules, Typer, or prompt-toolkit.

## Verification

Focused tests cover public/root exports, provider creation, provider-free saved
resume, exact hidden prewarm, refresh dominance, complete DTO projection,
split Apply, all-preserved completion, exact retry recovery, Source and
workbench conflicts, Save As-plan rejection, provider/error projection, and
fresh-process import isolation.

The integrated structural Atomize suite passed 178 tests. One additional existing
Study test currently fails because the registered `mem atomize` command in the
tested baseline has no `--memory` option; this public API change does not touch
command registration or that test's focused-prewarm behavior.

A wheel built from the change was installed into a new Python 3.13 environment
and exercised outside the checkout. The smoke used the installed
`site-packages` origin, produced `PROVIDER` then provider-free `SAVED`, called
the provider once, split one Memory, recorded one checkpoint, and recovered the
same checkpoint when the exact proposal was applied again.

## Intentional non-goals

- no provider prompt, decoder, classification, or saved-schema change;
- no new structural Atomize agent or MCP tool in this slice;
- no public workbench response-editing or reanalysis API;
- no public Save As method; and
- no expansion from local ordinary Contexts to Grant-authorized mutation.

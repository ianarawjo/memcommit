# Structural Atomize public Python API

Last reviewed: 2026-08-29.

## Contract

`MemCommitClient` exposes Atomize as a structural lifecycle:

```python
proposal = client.open_atomize_analysis(
    context_name=None,
    refresh=False,
    use_prepared=True,
    memory_selector=None,
)
plan = client.plan_atomize_output(
    proposal.context_name,
    expected_version=proposal.version,
    output_context_name="atomized/output",
)
receipt = client.save_saved_atomize_as(
    proposal.context_name,
    expected_version=plan.proposal.version,
)
```

The in-place alternatives are `apply_atomize_as_is(proposal)` and stateless
`apply_saved_atomize_as_is(context_name, expected_version=...)`.

The proposal projects the overview, ordered source classifications, proposed
children and evidence, read-only issues and possible readings, exact Output
plan, terminal completion state, and opaque version. It exposes no answer,
selected reading, response text, review-edit readiness, or response-reanalysis
readiness. `AtomizePlanUpdateResult` is the sole provider-free edit result.

## Open, planning, and Apply

Open returns one exact origin: `SAVED`, `EXACT_PREWARM`, or `PROVIDER`.
Opening never edits the Source Context. `refresh=True` explicitly requests a
new provider analysis; `use_prepared=False` disables hidden prepared lookup.

Output planning is provider-free and exact-version bound. A distinct Output
name is require-new and remains only a plan. Apply rechecks the exact Source,
analysis, and workbench revision, runs normal-form verification, and either
creates/reuses one in-place checkpoint or publishes one require-new Save As
Context/checkpoint. Repeating the exact final request after a lost response
recovers the same checkpoint.

Open ambiguity and conflict are audited as `AS_IS`; silence is never converted
to an answer. All-preserved output remains a deliberate recorded Atomize
completion.

## Removed routes

The public client no longer exposes response update, response reanalysis,
compound incorporate-and-apply, or Atomize Grounding methods. Their DTOs,
operation adapters, errors, and root exports are also absent. Keeping those
methods would make disambiguation and resolution part of the Atomize contract.

Old workbench response fields and Grounding records remain readable through
internal legacy model/Store paths for checkpoint and research-history
compatibility. They are not projected as current API capability.

## Error and dependency boundary

The taxonomy remains `AtomizeInputError`, `AtomizeContextError`,
`AtomizeProviderFailure`, `AtomizeConflictError`, `AtomizeStorageError`, and
`AtomizeExecutionError`. The facade imports its operation adapter lazily and
does not load commands, Typer, or prompt-toolkit.

## Verification and limits

Focused tests cover exports, lazy imports, whole/focused open, saved/prepared
reuse, refresh, read-only issue projection, Output planning, both Apply
directions, lineage, unresolved audit, recovery, stale conflicts, and the
absence of response/Grounding methods. Resolution of those findings is an
intentional non-goal of this API.

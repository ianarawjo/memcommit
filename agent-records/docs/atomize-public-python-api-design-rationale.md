# Structural Atomize public Python API

Last reviewed: 2026-08-15.

## Problem

Structural Atomize had a complete CLI/TUI lifecycle, but callers otherwise had
to import mutable workbench, session, Store, prewarm, and checkpoint internals.
That would make each adapter reconstruct cache policy, response semantics,
stale-state checks, Save As recovery, and application authority differently.

The public boundary therefore exposes immutable projections and typed use
cases while retaining the exact analysis/workbench pair behind an opaque
revision.

## Complete public lifecycle

`MemCommitClient` exposes:

```python
proposal = client.open_atomize_analysis(
    context_name=None,
    refresh=False,
    use_prepared=True,
    memory_selector=None,
)
response = client.update_atomize_response(
    proposal.context_name,
    expected_version=proposal.version,
    issue_uid=proposal.issues[0].uid,
    option_uid=None,
    comment="Treat the facts independently.",
)
reanalyzed = client.reanalyze_atomize_responses(
    proposal.context_name,
    expected_version=response.proposal.version,
)
plan = client.plan_atomize_output(
    proposal.context_name,
    expected_version=reanalyzed.version,
    output_context_name="reviewed/output",
)
receipt = client.save_saved_atomize_as(
    proposal.context_name,
    expected_version=plan.proposal.version,
)
```

The alternate final paths are `apply_atomize_as_is(proposal)`, stateless
`apply_saved_atomize_as_is(context_name, expected_version=...)`, and the
explicit compound `incorporate_and_apply_atomize(...)`.

## Open and cache contract

Open resolves the existing local Context once and returns one exact origin:

- `SAVED`: current durable pair reused without a provider;
- `EXACT_PREWARM`: exact hidden Study artifact materialized as the ordinary
  durable pair without a provider; or
- `PROVIDER`: one complete analysis produced and saved.

`refresh=True` requests provider analysis and dominates prepared reuse.
`use_prepared=False` disables hidden lookup, not exact saved-session reuse.
`memory_selector` focuses one exact Memory and disables whole-Context prepared
reuse. Open never edits the Source Context.

The proposal includes the overview, ordered classifications, children and
evidence, issues, selected readings and response text, Output plan, available
application direction, exact `review_edit_allowed` and
`response_reanalysis_allowed` readiness, terminal completion state, and opaque
version. These are projections of operation validation rather than adapter
heuristics.

## Review-update and reanalysis contract

Response and Output changes are provider-free exact-version use cases. A
response update replaces the whole selected choice/comment pair; both empty
clears it. A distinct Output name must be creatable and remains only a plan.
Every changed edit returns a new version; an unchanged edit returns the same
one.

Reanalysis requires at least one answered unary response. It sends the complete
declared unary frames in one provider turn, preserves the Output plan, and
publishes no partial result. Pair-shaped conflicts remain review evidence. The
runtime compares the original analysis/workbench pair under its session lock
before replacing both records; a concurrent edit causes
`AtomizeConflictError` and remains intact.

## Application and recovery contract

In-place Apply and Save As consume the exact reviewed proposal:

- `COMPOSITE` splits in place; other classifications preserve source identity;
- silence remains open and is audited as `AS_IS`, never inferred as an answer;
- all-preserved output still records deliberate completion;
- Source, graph safety, analysis, and workbench revision are rechecked;
- Save As is require-new, leaves Source unchanged, creates one final Atomize
  Context/checkpoint unit, records lineage, and selects the output; and
- repeating the exact final action after a lost response recovers the same
  checkpoint without a second effect.

The preterminal recovery exception admits only the terminal receipt appended
to the accepted workbench. Any other analysis, response, Output, layout, or
Source change is a conflict. `incorporate_and_apply_atomize` is one explicitly
chosen provider reanalysis followed by the resulting in-place or Save As path;
separate reanalysis remains available when a person must inspect the new
proposal before materialization.

## Error and dependency boundary

The public taxonomy is `AtomizeInputError`, `AtomizeContextError`,
`AtomizeProviderFailure`, `AtomizeConflictError`, `AtomizeStorageError`, and
`AtomizeExecutionError`. Invalid versions fail before Store access. Endpoint
construction/transport failures stay distinct from invalid semantic output.

The facade imports the operation adapter lazily. DTO imports and client
construction do not load commands, Typer, prompt-toolkit, or the structural
runtime. The operation adapter receives `ClientRuntime` and never reaches back
through `MemCommitClient`.

## Verification and intentional limits

Focused tests cover exports, lazy imports, whole/focused open, saved and exact
prewarm reuse, refresh, complete projection, response replace/clear, Output
planning, provider reanalysis, concurrent-edit CAS, in-place and Save As
effects, lineage, all-preserved completion, exact retry recovery, stale/source
conflicts, provider failures, and agent-registry composition. The installed
wheel smoke independently verifies provider-free saved review, review edits,
both final directions, and checkpoint recovery through MCP stdio.

This slice deliberately does not change prompts, decoders, classifications, or
saved schemas; expand to Grant-authorized mutation; treat pair conflicts as
unary guidance; or merge structural Atomize with conversational Grounding.

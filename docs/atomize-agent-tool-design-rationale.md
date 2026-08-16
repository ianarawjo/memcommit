# Structural Atomize agent tool design rationale

Last reviewed: 2026-08-15.

## Motivation and selected contract

An MCP request cannot retain the private Python proposal object used by the
CLI/TUI. Reconstructing acceptance from public IDs, or implementing review
logic in the transport, would create a second cache, stale-state, and
application policy. `memcommit_atomize` therefore projects the complete
structural lifecycle through seven strict version-1 actions, each delegating to
one stable `MemCommitClient` method:

| Action | Provider | Durable Context effect | Purpose |
| --- | --- | --- | --- |
| `open` | saved/prepared hit: no; miss/refresh: yes | none | open whole-Context or focused exact-Memory review |
| `respond` | no | none | replace or clear one exact issue response |
| `plan_output` | no | none | select in-place Source or require-new Save As destination |
| `reanalyze` | yes | none | incorporate answered unary guidance |
| `apply_as_is` | no | one Source checkpoint | apply the exact current in-place proposal |
| `save_as` | no | one new-Context checkpoint | publish the exact reviewed require-new plan |
| `incorporate_and_apply` | yes | one Source or new-Context checkpoint | perform one explicitly approved compound action |

The adapter does not import commands, TUI code, Store internals, or Atomize
runtimes. The frozen registry and MCP transport expose the same schema and
JSON-safe result.

## Cache, provider, and effect reporting

`open` preserves the operation's existing policy. `SAVED` and
`EXACT_PREWARM` set `cache_used: true`; only `PROVIDER` sets
`provider_used: true`. Saved open reports `effect: NONE`; prepared
materialization and provider analysis report `DERIVED_SESSION`. A focused
`memory_selector` cannot silently reuse a whole-Context prepared artifact.

`refresh: true` explicitly requests a provider analysis and dominates
`use_prepared`. Provider-free response and Output edits return the complete new
proposal and opaque version. Reanalysis and compound incorporation state their
provider use directly. Final Apply and Save As report
`effect: CONTEXT_CHECKPOINT`; planning Save As alone creates nothing.

## Exact-version review boundary

Every saved action consumes the exact 64-character version returned by the
previous proposal. The token binds the immutable analysis and the complete
workbench record, including responses, Output plan, layout, and terminal
receipt. Action `allowed` values are projected from the same workbench
validation, including pair/multi-response restrictions and terminal state,
rather than reconstructed in the adapter. A stale action cannot overwrite a
concurrent review edit.

`respond` is replacement, not patch, semantics. `option_uid: null` plus an
empty comment clears a response. `plan_output` validates a distinct name as
require-new before changing the workbench. `reanalyze` admits only answered
unary frames; pair-shaped conflict responses remain visible review evidence
and are not flattened into unary semantic input. Provider results replace the
analysis/workbench pair under one Context-scoped compare-and-swap, so a
response changed during inference wins and no partial new pair is published.

## Application and retry boundary

`apply_as_is` is allowed only for an in-place plan. `save_as` is allowed only
for a distinct reviewed Output name. Save As leaves Source unchanged, creates
the new Context as one Atomize creation/checkpoint unit, records Source
lineage, and conditionally selects the output. It does not accept an existing
destination.

A lost final response may repeat the exact same `apply_as_is` or `save_as`
payload. The public boundary accepts only the original preterminal revision
plus the exact terminal receipt produced by that action, then returns the same
checkpoint with `recovered: true`. Any response, Output, layout, analysis, or
other workbench change is `stale_state`. The compound action deliberately does
not promise byte-for-byte transport retry after its provider turn; callers
that need an inspectable intermediate proposal use `reanalyze` followed by a
separately approved final action.

## Error and Skill boundary

Strict parsing rejects unknown fields, invalid action shapes, and malformed
versions before public execution. Provider and internal details are redacted;
actionable input/Context messages remain visible. `stale_state` is
non-retryable and requires `open`, review, and fresh approval.

`skills/memcommit-atomize/` is host guidance, not another implementation. It
requires direct tool use, newest-version chaining, complete proposal review,
explicit approval, bounded exact final-action retry, and the separate
`memcommit_atomize_grounding` tool for conversational issue resolution. The
Skill passes the canonical Skill Creator validator.

## Verification and limits

Focused public/agent tests cover all seven actions, strict schema projection,
focused Memory open, saved/prepared/provider origins, provider-free review
edits, response clearing, require-new validation, atomic reanalysis under a
concurrent response edit, in-place and Save As materialization, checkpoint
lineage, exact retry recovery, stale rejection, and one-public-call adapter
ownership. The installed-wheel MCP smoke covers saved open, response edit,
Output planning, in-place Apply, reviewed Save As, both exact recovery paths,
and independent Store verification without an external provider.

This is local ordinary-Context and local stdio evidence. It does not claim
remote authentication, Grant-authorized mutation, provider-backed installed
execution, native Windows behavior, or automatic Skill installation.

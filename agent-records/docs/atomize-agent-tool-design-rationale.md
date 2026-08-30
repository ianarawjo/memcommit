# Structural Atomize agent tool design rationale

Last reviewed: 2026-08-29.

## Selected contract

`memcommit_atomize` projects four strict version-1 actions, each delegating to
one stable `MemCommitClient` method:

| Action | Provider | Durable Context effect | Purpose |
| --- | --- | --- | --- |
| `open` | saved/prepared hit: no; miss/refresh: yes | none | inspect whole-Context or focused exact-Memory analysis |
| `plan_output` | no | none | select in-place Source or require-new Save As destination |
| `apply_as_is` | final normal-form verification only | one Source checkpoint | apply the exact current in-place proposal |
| `save_as` | final normal-form verification only | one new-Context checkpoint | publish the exact require-new plan |

The JSON result includes immutable issue evidence and possible readings but no
answer state or response action. The registered schema does not contain
`respond`, `reanalyze`, or `incorporate_and_apply`, and there is no separate
`memcommit_atomize_grounding` tool.

## Cache, version, and effect boundary

`SAVED` and `EXACT_PREWARM` report cache use; only `PROVIDER` analysis reports
provider inference. Every non-open action consumes the exact 64-character
version returned by the previous proposal. `plan_output` returns the complete
new proposal/version without creating a Context. Final Apply and Save As report
`CONTEXT_CHECKPOINT` and may recover an exact earlier success.

The token continues to bind the complete durable workbench record, including
legacy fields, so a concurrent or forged write cannot be ignored. Binding a
field for stale-state safety does not make that field an editable public
capability.

## Skill boundary

`skills/memcommit-atomize/` instructs a host to inspect read-only findings,
chain the newest exact version, plan only the requested Output, and materialize
only after approval. When an issue needs resolution, the host reports its
evidence and leaves follow-up to the caller. It does not route to shell access,
a Grounding tool, or another operation automatically.

## Verification and limits

Tests cover all four actions, strict unknown-action rejection, cache/provider
origin, exact planning, both checkpoint directions, retry recovery, stale
rejection, registry composition, and absence of the retired Grounding adapter.
The tool currently covers local ordinary Contexts. It does not define the
future consumer of an unresolved Atomize receipt.

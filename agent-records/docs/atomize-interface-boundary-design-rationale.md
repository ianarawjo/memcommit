# Atomize console presentation ownership

> **Superseded console layout (2026-08-30):** the Atomize workbench package was
> removed. Its non-applying screen now belongs to `commands/atomize/impact.py`,
> its completed report belongs to `commands/atomize/review.py`, and retained
> discovery belongs to `commands/atomize/records.py`. The earlier extraction
> details below remain historical evidence.

Last reviewed: 2026-08-29.

## Selected boundary

Atomize's console adapter owns two distinct projections over the same typed
operation evidence:

```text
Atomize domain/application/runtime
        |
        +-- commands/atomize/workbench/
        |      interactive or snapshot analysis projection
        +-- commands/atomize/receipt.py
               post-Apply effect and unresolved-evidence receipt
```

`commands/atomize/workbench/screen.py` projects the saved analysis through the
shared Result and Resolution shells. Atomize findings are read-only: the screen
has no choice selection, response composer, response persistence, reanalysis,
or Grounding action. Before Apply, the operation command may use the shell for
its own exact Output/Apply workflow; after Apply, `mem review atomize` forces
the same evidence into a provider-free read-only view.

The workbench screen is the single analysis presenter for both interactive and
plain snapshot routes. Apply receipt rendering lives in
`commands/atomize/receipt.py` so analysis presentation cannot silently acquire
checkpoint or materialization semantics. The receipt receives a typed
`AtomizeApplicationAudit`, not an unstructured count dictionary.

Every unresolved receipt item uses the shared
`terminal.components.findings.issue_one_line_presentation` component. That
component owns the one-logical-line text and semantic token styling, while
Atomize owns classification and projection of its audit records.

There is no `commands/atomize/grounding.py`. The removed interface and facade
paths are not compatibility shims, and no legacy data model or Store handler
remains, as described in
[`atomize-grounding-application-boundary-design-rationale.md`](atomize-grounding-application-boundary-design-rationale.md).

## Invariants

1. Presentation modules do not call the provider or mutate a Context.
2. A read-only Review navigation turn never saves a workbench draft.
3. The command invokes typed application/runtime use cases for Apply and Save
   As; a screen action is not itself mutation authority.
4. `ATOMIZE_UNCERTAINTY` is shown as `AMBIGUITY` without rewriting durable
   analysis data.
5. The Apply receipt prints every unresolved item, in saved order, on exactly
   one untruncated logical line.
6. TTY color and plain output retain identical labels, ordering, identities,
   and issue boundaries.
7. No Atomize presenter imports or depends on a later resolution/update
   operation.

## Alternatives considered

Keeping Apply receipt code in the analysis renderer was rejected because the
typed application audit and checkpoint handoff are a separate lifecycle.
Keeping a second plain analysis renderer was rejected because it had no caller
and duplicated the workbench screen's snapshot responsibility.
Keeping a Responses frame disabled by policy was rejected because it would
continue to advertise response semantics that Atomize no longer owns.

A structured resolution handoff was not added. The receipt is durable evidence
without defining the schema or lifecycle of a future consumer.

## Verification

Boundary tests assert the removed Grounding presenter is absent and that the
Atomize command delegates to its workbench and receipt owners. Snapshot and PTY
tests prove the analysis/detail/review surfaces have no Responses frame.
Receipt tests prove all unresolved audit items use the shared one-line
presentation. The ordered 180×52 record is stored under
`agent-records/docs/screenshots/atomize-read-only-findings-20260829/`.

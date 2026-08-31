# Legacy Ground Model Retirement Rationale

## Motivation

The original Ground prototype persisted a parallel JSON aggregate named
`GroundSession`. It described Goals, bound Context frames, proposed Rules,
Cases, review state, dialogue state, and optimistic-concurrency metadata. The
later physical Ground design represents those same durable product concepts as
one ordinary Context-rooted workspace with `goals`, `rules`, `examples`,
`contexts`, and `relations` children.

The repository was never distributed, the active local Store contained no
`ground-sessions/*.json` records, and no migration or public compatibility
contract was required. Retaining the old model would therefore preserve a
second product identity without protecting any data.

## Selected boundary

The `memcommit.application.operations.ground_workbench.ground.model` package and the
Ground-session Store have been removed. Physical Ground now has these owners:

- `ground/workspace_model.py` owns the Context-rooted manifest and workspace
  projection;
- `ground/contracts.py` owns operation-neutral Ground text limits, validation,
  errors, and frame digesting;
- `ground/workspace_application.py` owns creation and editing use cases; and
- Fit, Distill, Makemore, and Conformance consume a frozen physical workspace
  rather than branching on `GroundSession`.

No compatibility facade preserves the deleted import path. A missing
`ground-sessions/` directory is normal, and Store rename, lock,
write-protection, profile, and study-bundle code no longer scans or rewrites it.

## Semantic boundary

Physical Ground examples are ordinary proposition Memories, not legacy
input/expected-output Case records. Ground Conformance therefore checks those
example propositions against the workspace Rules through the ordinary Context
Conformance contract; it does not fabricate an expected output. Fit, Distill,
and Makemore likewise project only the physical lanes they actually consume
and revalidate those lanes around provider work.

The removed JSON schema, review transitions, named shell, and session dialogue
remain visible only in historical design records and screenshots. They are not
runtime compatibility promises and must not be reintroduced as a second Ground
model.

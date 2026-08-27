# Ground Model Package Design Rationale

## Motivation

The Ground application model combined durable schema records, whole-session
relationship validation, and session state transitions in one 2,440-line
module. Those responsibilities change for different reasons: records define
the persisted vocabulary, validation protects invariants across those records,
and session actions produce the next reviewed state. Keeping them together
made each responsibility harder to identify without providing a behavioral
benefit.

## Selected boundary

`memcommit.application.operations.ground.model` is now a package with three
owners:

- `records.py` owns constants, value types, record-local parsing, and durable
  serialization.
- `validation.py` owns reconstruction and invariants that require the complete
  Ground session, such as reciprocal Rule/Memory links, frame uniqueness, and
  revision consistency.
- `session.py` owns pure state transitions such as binding a workbench,
  proposing or reviewing items, and revising requirements.

The package `__init__.py` preserves the established
`memcommit.application.operations.ground.model` import surface. `GroundSession`
keeps its `from_dict` entry point and delegates to whole-session validation by
a local import. This keeps records as the foundational vocabulary without
creating an import cycle while validation constructs the same record type.

## Compatibility and safety boundary

This change intentionally preserves schema versions, serialized fields,
digests, validation failures, revision behavior, and public symbol identities.
It does not change Ground authority, persistence, provider calls, workspace
I/O, or console/TUI presentation. Those integrations continue to consume the
same facade, so callers do not need to migrate as part of the structural split.

Record-local validation remains beside each record rather than being moved
wholesale into `validation.py`; only checks that need the complete session are
owned there. The split is therefore a responsibility boundary, not an attempt
to redesign the Ground domain or its persisted contract.

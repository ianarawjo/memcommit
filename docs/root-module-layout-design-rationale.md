# Root module layout design rationale

## Problem

At baseline commit 885e62c0, all 249 top-level Python modules in memcommit
shared one flat directory. Operation implementations, public package
boundaries, reusable concepts, and historical import facades therefore looked
equally authoritative during repository exploration.

The immediate goal is navigability, not a behavioral redesign. A later reader
must be able to open an operation package or a named shared concept and find
the implementation that owns it without first knowing the repository history.

## Invariants

- Function and class bodies do not change as part of relocation.
- Existing root import paths remain available through module-identity aliases.
- Internal implementation imports point at canonical owner modules after each
  relocation batch.
- One source implementation has exactly one canonical path.
- Public Context, Store, in-memory Ops, CLI, bootstrap, and documented Context
  locator boundaries remain at the package root in this pass.
- Existing behavioral failures are not silently converted into new contracts.
  Baseline failures remain a comparison set during path-only work.
- Operation evidence state remains authored only in the existing evidence
  registries; this layout record does not classify route closure.

## Classification

Every baseline root module has one role:

- compatibility-facade: an already migrated historical import path;
- operation-implementation: code named for and consumed by one operation
  family;
- shared-concept-implementation: reusable code with a narrower named owner;
- root-boundary: one of the deliberately retained public or composition
  boundaries.

The complete frozen classification is in
root-module-relocation-plan.json. Its Markdown projection exists for reading,
while the JSON preserves exact paths for mechanical checks.

## Compatibility boundary

Relocated modules leave a root file that imports the canonical module and
places that exact module object in sys.modules under the historical name. This
preserves object identity and keeps legacy monkeypatch paths attached to the
implementation. It does not promise that module names are permanently public;
removing those aliases is a separate compatibility decision after repository
reading establishes which paths have real consumers.

## Verification

The pre-relocation full suite and its exact failing node IDs form the behavioral
baseline. Each relocation batch must collect successfully, keep focused tests
passing, and introduce no new behavioral failure. Static ownership tests and
generated callable catalogs may change because their subject is the path
layout itself; those records are updated only after the canonical moves settle.

## Non-goals

This pass does not rename callables, split large modules, consolidate duplicate
policies, decide whether compatibility aliases can be deleted, or resolve the
known functional failures. Those require semantic reading after the package
layout makes the relevant code traceable.

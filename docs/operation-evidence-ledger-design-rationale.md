# Operation evidence ledger design rationale

## Problem

Operation boundary work produced useful focused matrices and rationale notes,
but their status was repeated in the distribution plan, the shared consistency
matrix, the generated route catalog, and individual documents. Most operation
matrices also live in one flat `docs/` namespace. Moving them now would break
historical links, while continuing to copy status between ledgers would let a
review conclusion become stale without an obvious failure.

## Canonical records

[`operation-route-classification.json`](operation-route-classification.json) is
the sole authored source of operation-level route state. It covers exactly the
canonical operations exposed by Help. A reviewed operation records one of
`CLOSED`, `MIXED`, `LEGACY`, or `N/A` plus a nonempty conclusion;
`UNREVIEWED` means only that no route-closure conclusion has been made.

[`operation-evidence-index.json`](operation-evidence-index.json) is the sole
authored operation-to-document index. It also covers the exact Help operation
set and can register incomplete evidence for an operation that remains
`UNREVIEWED`. The version-1 classification schema still repeats evidence paths
for reviewed states because the callable catalog consumes that shape; the
verifier requires those compatibility fields to match the evidence index
exactly, preventing the duplicate representation from drifting.

[`generated/operation-evidence-index.md`](generated/operation-evidence-index.md)
is the human-readable projection of both registries. It is regenerated rather
than edited. The generated callable and operation-route catalogs remain
mechanical source inventories; they may project the canonical state but do not
own it.

[`operation-consistency-matrix.md`](operation-consistency-matrix.md) owns a
different level of evidence: shared contracts such as authority, cache,
receipt, Apply, and terminal interaction. Its contract states describe the
cross-operation migration, not whether one operation route is closed. The
distribution plan similarly owns workstream ordering and future gates, not a
second operation-status table.

## Update transaction

For each operation, keep its focused boundary matrix and rationale separate
while the architecture is still being learned. In the same change that reaches
a route conclusion:

1. create or update the focused evidence without moving existing documents;
2. register every focused document under that operation in
   `operation-evidence-index.json`;
3. update `operation-route-classification.json` only when the reviewed route
   conclusion changes;
4. update only the applicable shared-contract rows in the consistency matrix;
5. run `python scripts/verify_operation_evidence.py` to regenerate the index;
6. run `python scripts/verify_operation_evidence.py --check` and its focused
   tests before committing.

A new final operation matrix uses either
`<operation>-application-boundary-matrix.md` for an internal application slice
or `<operation>-callable-boundary-matrix.md` for a reviewed vertical package
that includes its exposed adapters. A joint matrix may name multiple
operations when it deliberately owns one shared implementation, as with
Distill and Elaborate; every operation still registers that same evidence
explicitly.

## Enforced invariants

The verifier fails when:

- Help, the classification registry, and the evidence registry contain
  different operation sets;
- an operation is classified more than once;
- reviewed evidence is missing, duplicated, unsafe, or outside `docs/`;
- a root operation boundary matrix is not in the evidence index or uses an unsupported
  final filename;
- a local link in a governing ledger or registered Markdown evidence file is
  broken;
- an authored common ledger hard-codes aggregate operation-state counts; or
- the generated evidence index is stale.

CI runs the same check, so local and hosted verification use one contract.

## Alternatives and migration boundary

Moving every matrix into a new per-operation directory was rejected for this
stage because it would create a large link migration unrelated to behavioral
verification. Maintaining a second hand-written Markdown index was also
rejected because it would reproduce the drift this change is intended to
prevent.

The current flat documents therefore remain in place. Operations continue to
be reviewed and recorded individually. A later consolidation may group their
documents after naming roles and operation boundaries stabilize; that change
must migrate registry paths and links atomically and must not reinterpret the
recorded conclusions.

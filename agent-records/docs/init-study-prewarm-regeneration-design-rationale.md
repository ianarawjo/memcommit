# Legacy Study prewarm regeneration design rationale

> Historical design: the prewarm implementation was removed on 2026-09-06.
> Scenario data and ordinary sessions remain; see [retirement rationale](study-prewarm-retirement-design-rationale.md).

## Current boundary

The prewarm registry and regeneration modules belong to the packaged `legacy`
scenario. They preserve the exact semantic artifacts and compatibility logic
used by historical regression sessions. They are not part of `mem init-study`:
initialization publishes a clean participant/authority pair without validating,
regenerating, or attaching a shared prewarm bundle.

## Historical motivation

Earlier Legacy runs pinned immutable semantic-prewarm bundles. Compatibility
validation had to distinguish current artifacts, explicitly supported older
contracts, and malformed or unknown generations. Regeneration used production
operation validators, complete matrix coverage, content-addressed artifacts,
and atomic registry publication so an obsolete cache could never become a
participant result merely because its bytes were readable.

Those properties remain in `study_scenarios.legacy.prewarm` for research tools
and exact-registry regression tests. They continue to fail closed on unsafe
paths, digest mismatch, incomplete coverage, unknown schema generations, or a
provider result that violates the operation contract.

## Why initialization no longer invokes it

The former path depended on a registered editable `study-baseline`, held the
Profile registry lock across potentially long provider work, and attached a
shared cache as part of provisioning. Once Legacy became a self-contained
packaged scenario, that behavior would make `--scenario legacy` depend on
mutable external state and provider availability. It also made setup publish
more than the requested clean scenario data and authority topology.

The selected boundary keeps scenario materialization deterministic and fast.
Prewarm generation, inspection, and historical bundle analysis are explicit
research activities; they cannot silently change what `init-study` installs.
Previously initialized runs and recorded bundle digests are not rewritten.

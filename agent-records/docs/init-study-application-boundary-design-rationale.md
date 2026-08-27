# Init-study application boundary design rationale

## Selected boundary

`operations/init_study/model.py` owns the result type,
`composition.py` turns one packaged scenario into participant and authority
stores, `publication.py` materializes Grants and atomically publishes the pair,
and `application.py` selects `coffee` or `legacy` and coordinates the workflow.
The console command owns only argument validation, receipts, and action-ledger
presentation.

`operations/profile` remains reusable control-plane infrastructure: Profile
validation, registry locking and replacement, store inspection, Grant
materialization, and legacy split-Study administration. It no longer owns a
Study baseline importer or compatibility facade for initialization. Production
callers import the `init_study` operation directly.

## Invariants

- One initialization publishes exactly one participant Profile, one authority
  Profile, and all scenario Grants in one registry generation.
- The participant becomes active; the authority Profile is never selected.
- A failure before registry publication leaves no partial pair. If replacement
  becomes visible but final durability confirmation fails, both stores remain
  so the registry cannot point at missing data.
- Scenario inputs are staged privately, validated, copied without operational
  history, and removed after publication.
- Neither scenario depends on a registered source Profile or installs a shared
  semantic prewarm.

## Limitation

Composition still calls narrow Profile-owned helpers for the established
Legacy package and Grant schemas. Moving those reusable primitives into
smaller Profile modules is separate from removing the public baseline
lifecycle and was intentionally not combined with this change.

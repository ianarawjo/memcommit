# Init-study application boundary design rationale

## Motivation

The `init-study` CLI adapter already had its own command package, but the
operation's run composition, atomic publication, and result model lived at
the end of `operations/profile/model.py`. That made the Profile control plane
own both reusable Profile primitives and one concrete provisioning workflow.
It also obscured the fact that `init-study` is an operation with its own
application boundary.

This change is an ownership refactor. It must not change the command grammar,
scenario data, Profile registry schema, Grant schema, durable store layout,
prewarm policy, or user-visible receipts.

## Selected boundary

`operations/init_study/model.py` owns the typed initialization result.
`operations/init_study/composition.py` snapshots a validated editable baseline
or materializes a built-in scenario, then composes its three Task inputs into
one participant store and one run-private authority store.
`operations/init_study/publication.py` stages those stores, materializes their
Grants, publishes both Profile roots, and replaces the registry as one locked
transaction.
`operations/init_study/application.py` selects the `coffee-v1` or `legacy-v1`
source and exposes the operation's public initialization functions.

`operations/profile` remains the owner of Profile validation, registry and
store lifecycle primitives, authority Grant primitives, and editable legacy
Study baseline import and refresh. The dependency therefore runs from the
concrete `init-study` workflow toward reusable Profile infrastructure.

## Preserved invariants

- One run still publishes exactly one participant Profile and one authority
  Profile, with all three Task namespaces composed inside those two roots.
- The participant Profile becomes active in the same registry generation that
  publishes the authority Profile and their Grants; the authority side is not
  selected.
- A failed batch publishes no partial pair. A registry replacement whose
  durability cannot be confirmed retains both stores rather than leaving
  visible registry entries pointing at missing roots.
- `coffee-v1` remains the default immutable virtual baseline. `legacy-v1` and
  `--from-profile` retain editable-baseline snapshot and prewarm behavior.
- Former `memcommit.profiles` initialization functions remain deferred
  compatibility shims and the relocated result type remains a compatibility
  alias, while new production callers import the operation-owned modules
  directly.

## Staged limitation

Composition and publication currently call narrow private helpers in
`operations.profile.model`. Promoting those reusable registry, inspection,
and Study-baseline primitives into smaller Profile-owned modules is a later
step. Performing that larger migration simultaneously would broaden a
behavior-preserving ownership change into a storage and compatibility
redesign. Legacy Study group administration also remains Profile-owned because
it is exposed by `mem profile`, not by `mem init-study`.

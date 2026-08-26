# Store root resolution design rationale

Last verified: 2026-08-15.

## Problem

Importing `memcommit.store` previously called `resolve_active_store_dir()` and
materialized every module-level path immediately. Because `memcommit.__init__`
exports `MemoryStore`, even `import memcommit` read the person's HOME Profile
registry. An explicit `MemCommitClient(root=...)` could therefore fail on an
unrelated or newer Profile registry before its already-authorized root was
processed.

The eager globals also made the active Profile an import-order side effect.
There was no Store instance at the point the selection was frozen, and a host
could not import the library safely before choosing an explicit boundary.

## Selected lifecycle

Store selection now has three distinct moments:

1. Import constructs path-compatible placeholders and performs no Profile I/O.
2. `MemoryStore(root=...)` freezes that explicit absolute root directly and
   never calls the active-Profile resolver.
3. `MemoryStore()` resolves the active Profile exactly once during construction
   and freezes the resulting Store root for the lifetime of that instance.

All instance path properties derive from the frozen root. A later global
Profile change therefore affects only a newly constructed Store, not an object
that may already hold snapshots, locks, or mutation intent.

The legacy module names such as `STORE_DIR` and `STATE_FILE` remain as lazy
path-like compatibility values because command helpers and test fixtures still
refer to them. Directly using one resolves the active Profile at that moment;
merely importing it does not. They are a compatibility surface, not the new
application ownership model. New code should prefer one caller-owned
`MemoryStore` and its path properties.

## Safety and compatibility boundaries

- Explicit roots retain their existing absolute-path normalization and create
  behavior.
- Profile-backed construction still fails closed on an absent, malformed, or
  unauthorized Profile configuration; the failure is delayed only until a
  Profile-backed Store is actually requested.
- Test and Study fixtures may continue replacing the module path names with
  concrete `Path` objects. A Store constructed under that replacement freezes
  the supplied root.
- A previous test expected an existing Store to follow a later `STORE_DIR`
  replacement. That expectation is intentionally reversed: the existing Store
  stays on its original ledger, while a new Store observes the new boundary.
- This change does not redesign Profile switching commands or remove the legacy
  globals. Migrating remaining direct global consumers is later cleanup.

## Rejected alternatives

- Catching Profile parse errors during import was rejected because it would
  silently choose an unintended Store.
- Falling back to `~/.mem` for explicit-root callers was rejected because no
  fallback is needed and it could conceal a boundary error.
- Re-resolving the active Profile on every Store property access was rejected
  because one object could change persistence targets between validation and
  mutation.
- Removing all path globals in this change was rejected because it would mix a
  broad command/test migration into the narrow initialization fix.

## Verification

Focused tests prove that an explicit root never calls the resolver, a
Profile-backed Store resolves once, old instances remain frozen while new ones
observe a changed selection, and an invalid HOME Profile does not prevent
package import or explicit-root client creation. Store, cache, Ground, Study,
and clipboard regressions protect the lazy compatibility paths.

The distribution gate repeats the installed-wheel MCP stdio smoke without an
isolated HOME. Because the server receives `--root`, an unrelated host Profile
registry must no longer affect initialization, discovery, Add, or its durable
checkpoint.

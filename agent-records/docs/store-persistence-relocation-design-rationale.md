# Store persistence relocation rationale

## Decision

The concrete Store implementation moves from the package root to
`memcommit.persistence.store`. The historical `memcommit.store` import remains
available through the centralized lazy submodule alias, while all repository
implementation imports use the canonical persistence owner.

## Reason

`MemoryStore` is central to MemCommit, but its responsibility is not the core
meaning of Memory or Context. It resolves an active storage root and performs
filesystem reads, JSON serialization, locking, atomic replacement, checkpoints,
session retention, and restoration. Those are durable-storage mechanisms, so a
root-level `store` implementation obscured the distinction between core models
and their persistence implementation.

The relocation is deliberately ownership-only. It does not change Store method
bodies, paths, Profile selection, lock ordering, compare-and-swap checks,
rollback, checkpoint formats, or public root exports. `memcommit.MemoryStore`
continues to resolve to the same class, and `memcommit.store` remains importable
for existing callers without leaving a physical implementation at the package
root.

## Dependency boundary

Repository code imports `memcommit.persistence.store` directly. Core and
application code may still depend on the broad Store during this transitional
pass; relocating the implementation does not claim that those dependencies are
already ports. A later decomposition may define narrow application-owned
repository contracts and split filesystem actors, but it must preserve the
existing atomicity and recovery invariants while migrating each caller.

## Rejected alternatives

- Moving Store under `core` was rejected because concrete filesystem and lock
  behavior is an implementation of persistence rather than a domain rule.
- Deleting `memcommit.store` immediately was rejected because it is an existing
  public persistence import with extensive callers; the centralized exact alias
  preserves that contract without retaining a physical facade.
- Combining the path move with a Store redesign was rejected so behavioral
  regressions remain distinguishable from ownership relocation.

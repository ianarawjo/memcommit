# Application authority container rationale

## Problem

The operation-neutral Grant and write-authority modules lived in a root-level
`memcommit.authority` package beside architectural layers. Their callers use
them to resolve granted Contexts and protect authorized Context use and
mutation, so the root placement obscured their role as shared application
policy.

## Decision

Relocate the complete package mechanically to
`memcommit.application.capabilities.authority`. This step changes physical ownership and
canonical imports only; it does not change permission semantics, persisted
schemas, callable names, or runtime behavior. No `memcommit.authority`
compatibility facade is retained.

The package remains separate from `application.operations` because its policy
is shared by many operations and public adapters rather than owned by one use
case.

## Boundary and limitation

`access.py` and `study_operation_policy.py` primarily express or coordinate
application authority. The former `derived_policy.py` was later retired when
Grant authorization was reduced to enforceable Context uses in
`application.authorization.context_use`. `storage_permissions.py` and
the durable registry mechanics in `write_protection.py` also contain POSIX,
locking, JSON, and filesystem persistence details. They move intact in this
step so the package relocation does not become a behavior-changing split.

A later extraction should move those storage mechanics under `persistence`
while leaving application-level authorization decisions here. Moving the
package under `application` does not claim that every contained function is
already free of persistence dependencies.

## Invariants

- The historical relocation itself preserved the then-current Grant and
  write-protection decisions; later policy changes are recorded separately.
- Internal callers use `memcommit.application.capabilities.authority` as the canonical
  package path.
- The application package initializer remains import-light.
- Storage and write-protection schemas remain byte-compatible.
- Persistence extraction is explicitly deferred to a separate change.

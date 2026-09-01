# Authorization and Context access ownership rationale

## Problem

Grant-aware Context resolution, operation authorization, and storage safety
mechanics once shared one package even though they answer three different
questions: what resource is addressed, whether a use is allowed, and how the
decision is preserved at the filesystem boundary. Keeping those concerns in
one container made callers depend on a broad authority concept instead of the
narrow responsibility they actually use.

## Decision

Split the former container by responsibility and remove it rather than retain
a compatibility facade:

- `memcommit.application.context_access` owns local and granted Context
  resolution, validated Grant views, readable catalogs, and navigation
  projections.
- `memcommit.application.authorization` owns Context-use decisions, operation
  snapshot guards, retained-checkpoint read authorization, and the retained
  analysis policy.
- `memcommit.persistence.store.infrastructure` owns private-storage permission
  enforcement and the durable write-protection registry.

Profile remains the owner of Grant creation, update, revocation, registry
lifecycle, and its registry lock. The split changes physical ownership and
canonical imports only; permission semantics, lock order, persisted schemas,
error behavior, and operation behavior remain unchanged.

## Boundary and limitation

Context access still consumes Profile registry data because a Grant is the
metadata from which a public Context view is resolved. That dependency does
not transfer Grant lifecycle ownership to Context access. Authorization still
uses the Profile registry lock when it must keep a validated Grant snapshot
stable through a write; the lock remains Profile-owned and the decision to
hold it remains authorization-owned.

This change intentionally does not rename domain vocabulary such as
`AuthorityGrant`, alter public command language, migrate persisted records, or
redesign the authorization algorithm. Those are semantic changes and are
outside this ownership-only split.

## Invariants

- Every internal caller imports the narrow owning module; the former broad
  package no longer exists.
- Grant resolution never itself authorizes an operation, and an authorization
  decision never invents or broadens a resolved Context.
- Profile owns Grant lifecycle; Context access owns Grant-backed views;
  authorization owns allowed-use decisions; persistence owns filesystem
  mechanics.
- The application package initializer remains import-light.
- Storage and write-protection schemas remain byte-compatible.
- Existing operation lock order and revalidation timing remain unchanged.

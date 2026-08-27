# Application operations container rationale

## Problem

MemCommit's application layer was physically split between a small
`memcommit.application` package containing operation-neutral execution and
review contracts and a much larger sibling `memcommit.operations` package
containing the operation-owned vertical packages. The sibling layout made the
operation implementations look like a separate architectural layer even
though their organizing responsibility is application use-case ownership.

## Decision

Relocate the complete `memcommit.operations` tree without internal refactoring
to `memcommit.application.operations`. The relocation changes only physical
ownership and canonical import paths. Existing module names, callable names,
function and class bodies, operation package boundaries, and runtime behavior
remain unchanged.

The nested `operations` segment is intentional. It keeps the first relocation
mechanical and makes the complete set of operation-owned packages visible
inside the application layer without forcing an immediate classification of
every module.

## Boundary and limitation

The relocated tree is still a set of vertical packages. Individual packages
continue to contain application contracts together with operation-owned
models, Store runtimes, provider implementations, caches, projections, and
other helpers. Their presence under `application.operations` does not assert
that every contained module is a clean application-layer module.

A later migration may extract those already established responsibilities into
`core`, `providers`, `persistence`, `configuration`, or adapter owners. That
work is deliberately excluded here because splitting mixed runtime and model
modules while changing the canonical package path would combine behavior and
ownership changes in one migration.

## Invariants

- Operation behavior and durable schemas do not change.
- Internal callers use `memcommit.application.operations` as the canonical
  package path.
- No `memcommit.operations` package facade is retained; historical flat root
  aliases continue to resolve directly to the new canonical modules.
- The application package remains import-light; its initializer does not
  eagerly import operation packages.
- Existing operation package and module boundaries remain intact during this
  relocation.

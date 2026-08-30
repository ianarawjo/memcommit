# Application operation and capability layout

## Problem

The application package had already collected operation-owned vertical slices
under `operations/`, while cross-operation policy, execution, review, history,
semantic, evaluation, and provisional root modules remained beside that one
clear category. A reader could not tell from the first package level whether a
module belonged to one operation or was intended to serve several operations.
Broad names such as `semantic` made that ambiguity worse, but decomposing those
owners before their consumers and invariants are reviewed would mix a physical
layout change with behavioral ownership decisions.

## Decision

The application root now has two implementation categories:

```text
memcommit.application
  operations
  capabilities
```

`operations/` remains the owner of user-meaningful vertical slices. Every
other pre-existing application package and root module moves intact beneath
`capabilities/`. The move is deliberately mechanical: it establishes the
scope distinction without asserting that every staged capability has its
final name, granularity, or architectural owner.

`capabilities` is preferred to `shared` because reuse alone is not ownership.
The later review must name each retained child after the invariant or lifecycle
it provides and must return code used by only one operation to that operation.

## Staging boundary

The initial capability container includes `authority`, `resolution`,
`retained_history`, `reviewing`, `semantic`, `semantic_execution`, evaluation
support, and the former application-root modules. In particular:

- `semantic` is retained only as a staging package and is expected to be
  decomposed into narrower capabilities;
- evaluation support is not thereby declared part of the production
  application kernel;
- `ops.py` still mixes structural rules, operation wrappers, and legacy
  behavior, so its later core and operation extractions remain necessary; and
- Store-, provider-, presentation-, and operation-facing dependencies already
  present inside these modules are unchanged and remain subjects of the next
  ownership review.

This staging move therefore creates no general permission for a capability to
import an operation or adapter. The intended long-term direction is
`operations -> capabilities`, with capability-to-operation and
capability-to-presentation dependencies removed as focused contracts are
established.

## Compatibility and import boundary

Repository-owned imports, package-data declarations, architecture scripts,
tests, and maintained design records use
`memcommit.application.capabilities.*`. No compatibility modules retain the
former `memcommit.application.<owner>` paths. This follows the repository's
existing internal-path policy: one implementation has one canonical physical
owner, and unsupported historical Python paths do not remain as a second
vocabulary.

Package initializers remain import-light. The relocation changes no callable
body, durable schema, provider payload, terminal behavior, operation route, or
public CLI name.

## Verification

The layout gate requires `operations`, `capabilities`, and `__init__.py` to be
the complete visible application root; verifies the staged capability member
set; rejects old application module paths from production source; and proves
in a fresh interpreter that the former paths are unavailable. Existing
operation, semantic-execution, authority, resolution, history, review, and
package-import tests continue to exercise behavior through the new canonical
paths.

## Next review

Review the capability container by change reason and invariant rather than by
filename similarity. A child remains a capability only when at least two
operations share its semantics, lifecycle, and failure boundary. The first
review should decompose `semantic`, identify adapter and persistence leakage,
and decide whether evaluation support leaves the application package entirely.
Command-review identity and operation projections have since moved to their
console owner.

## Follow-up: History decomposition

The staged `retained_history` package has since been fully decomposed. Shared
read-only reconstruction is now the `history` capability; Context snapshots
and checkpoint catalogs remain independent capabilities; command restoration
is `command_recovery`; Review and Revert logic returned to their operations;
and checkpoint codecs, lifecycle schemas, and terminal display moved to their
persistence or console owners. No `retained_history` compatibility facade is
kept, so the original staging name cannot become a second architecture.

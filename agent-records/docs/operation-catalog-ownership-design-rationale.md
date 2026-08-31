# Operation catalog ownership rationale

## Problem

The public operation descriptions had already moved out of the former
`memcommit.help_catalog`, but their intermediate owner remained
`memcommit.application.operations.operation_catalog`. That placement still
made the catalog look like one application operation's support data even
though application use cases and console, Python, and agent adapters all
consume the same MemCommit affordance.

The stronger operation-family fact was split off in console Help:
`HELP_CATEGORY_GROUPS` alone assigned all 66 operations to 11 ordered
families. Consequently application code, other adapters, catalog tooling, and
debugging checks could see operation descriptions but not the same family
membership that Help displayed.

## Decision

Relocate the stable metadata package to the top-level
`memcommit.operation_catalog`, beside `application` and `adapters`. Its subject
is the public operation set: typed identity, family, summary, flow, execution
kind, effect, range, maturity, selection guidance, and detailed explanatory
records. `OperationDescriptor` is the canonical record name; the historical
`OperationHelp` and `OPERATION_HELP_BY_NAME` spellings remain aliases within
the new owner, not separate implementations.

Move the 11 ordered family records into `operation_catalog.families`. Each
family has a stable identifier, display title, ordered operation membership,
intent description, and aggregate execution label. The catalog validates that
every public operation belongs to exactly one family, and every descriptor
carries that family's identity. Console Help derives its existing category
maps and ordering from those records rather than authoring a second registry.

A family may additionally declare complete ordered sections when its members
share a broad affordance but not one immediate interaction. `SEARCH & EXPLAIN`
is divided by affordance rather than by operation name. `RETRIEVE & ANSWER`
contains `find`, `search`, and `query`: each starts from an information need
and returns matching evidence or an answer grounded in it. `SYNTHESIZE`
contains `summarize` and `compare`: each starts from a selected whole Context
frame and constructs a new interpretation of one frame or two. Compare moves
here from the former `CHECK, COMPARE & REVIEW` family because it is a
two-frame synthesis rather than a quality or conformance check. The remaining
family is displayed as `CHECK & REVIEW`.
`HISTORY & RECOVERY` is likewise divided into `INSPECTION` (`log`, `diff`,
`trace`, `rationale`) and `RECOVERY` (`checkpoint`, `undo`, `redo`, `revert`).
Section membership must flatten to the family's exact operation order, and
each affected descriptor carries the stable section identity.

The Help operation remains under `memcommit.application.operations.help` and
depends on the catalog in one direction. Its composer still combines stable
operation meaning with interface-supplied command forms; the catalog imports
neither Help nor an adapter.

Reviewed operation `summary` and `best_for` translations follow the catalog.
Each non-English catalog lives under `operation_catalog/translations/`, and
`operation_catalog.localization` connects one canonical English record to the
requested language. Family descriptions and their translations also follow
the catalog because family intent is shared affordance meaning. Help-only
concepts, locator guidance, keyboard copy, CLI forms, and layout remain in the
console Help package because they describe that presentation.

## Boundary and limitation

The catalog is a descriptive contract for operation discovery and grouping.
Executable validation, authority, persistence, provider, and mutation rules
remain owned by each operation's implementation. Tests compare the catalog
with exposed operations, but the relocation does not make prose an executable
source of behavior.

This change preserves the public operation set and top-level Help family order.
It changes Compare's family membership and the Check family's display title,
but not Compare's execution, forms, authority, or result contract.
Family sections are descriptive affordance structure; they do not imply a
shared executable retrieval, synthesis, or history service and do not change
any operation's authority, determinism, or mutation contract.
It does not yet move the 66 application or console operation packages under
physical family directories, and it does not yet introduce executable trait
declarations for authority, history, provider, session, or mutation
requirements. Those changes can follow family by family after their shared
contracts are verified. No implementation remains under
`memcommit.application.operations.operation_catalog`.

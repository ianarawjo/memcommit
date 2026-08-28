# Operation catalog ownership rationale

## Problem

The typed descriptions of public MemCommit operations lived in the root-level
`memcommit.help_catalog` package. That name and location made the metadata look
like console Help presentation even though the same catalog is consumed by the
application Help operation, public API projections, semantic Help lookup, and
console command registration.

The package also contained `composer.py`, which does not define operation
metadata. It assembles catalog records with interface-supplied command forms
for Help presentation.

## Decision

Relocate the stable metadata package to
`memcommit.application.operations.operation_catalog`. Its subject is the
public operation set: typed identity, summary, flow, execution kind, effect,
range, maturity, selection guidance, and detailed explanatory records.

Move `composer.py` separately to
`memcommit.application.operations.help.composer`, because composition is Help
application behavior rather than catalog data. The Help operation depends on
the catalog in one direction; the catalog does not import Help or any console
adapter.

Reviewed operation `summary` and `best_for` translations follow the same
ownership. Each non-English catalog lives under
`operation_catalog/translations/`, and `operation_catalog.localization`
connects one canonical English record to the requested language. English is
not duplicated as a translation. Help-only category, concept, locator, and
keyboard copy remains in the console Help package because those strings
describe that presentation rather than an operation contract.

## Boundary and limitation

The catalog is a descriptive contract for operation discovery. Executable
validation, authority, persistence, provider, and mutation rules remain owned
by each operation's implementation. Tests compare the catalog with exposed
operations, but the relocation does not make prose an executable source of
behavior.

This change preserves the metadata values. Renaming the internal `catalog.py`
module or distributing canonical records beside every operation is
deliberately deferred. No compatibility facade remains at
`memcommit.help_catalog`, and no facade retains the former
`application.operations.help.localized_copy` path.

# Console selection component rationale

## Problem

The operation-neutral selection controls lived at `memcommit.selection`, even
though their state represents console cursor and checked-value interaction and
their renderers depend on the shared console text and terminal-theme grammar.
The root location made the package look like an application or domain concept.

Separating the package under a TUI-only owner would also preserve a boundary
that the console interface no longer has: line-oriented CLI presentation and
interactive TUI presentation share text safety, semantic color, option
identity, and selection projection.

## Decision

Relocate the complete package to `memcommit.adapters.interfaces.console.selection`.
Keep its pure option and state modules together with its current terminal
renderers so one console component owns the selection interaction vocabulary.
The relocation changes canonical import paths only; it does not change cursor,
checking, ordering, focus, marker, or rendering behavior.

## Boundary and limitation

Operation meaning, validation, executable-request construction, and durable
state remain with their callers. This package owns only process-local console
selection mechanics and presentation. The nested `tui` renderer package is
retained during this mechanical move and may be renamed later if the remaining
console layout vocabulary is consolidated.

No compatibility facade is retained at `memcommit.selection`.

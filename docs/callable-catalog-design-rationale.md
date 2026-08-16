# Mechanical callable catalog

Last reviewed: 2026-08-16.

## Problem

The operation consistency matrix records cross-operation contracts and the
operation-specific boundary matrices record reviewed vertical slices. Neither
view enumerates every private function, nested helper, method, class, or lambda
that can disappear from architectural review during a move. The distribution
and architecture plan therefore required a complete mechanically generated
callable catalog rather than another manually maintained list.

Runtime import introspection is not suitable for this inventory. Importing all
modules would assemble optional adapters, execute registration code, depend on
the host configuration, and still miss conditionally imported symbols. A raw
text search also cannot reliably distinguish declarations, aliases, methods,
or nested callables.

## Selected contract

[`memcommit._architecture_catalog`](../memcommit/_architecture_catalog.py)
parses every Python source file below `memcommit/` with the standard-library
AST and imports no MemCommit runtime module. The generated JSON Lines catalog
records, for every function, async function, class, and lambda:

- stable `module:qualified-name` identity;
- kind, public/private/local visibility, static export status, and package
  re-exports;
- normalized signature and decorators;
- repository-relative source path and exact start/end lines; and
- statically resolvable inbound call sites with caller, path, and line.

Nested functions use Python-style `<locals>` qualification. Lambdas include
their declaration line and column because they have no source name. The generated data is
sorted and contains no timestamp or absolute host path, so identical source
produces byte-identical output.

The same scan generates an operation route catalog from the canonical Help
operations and the Typer registrations in `memcommit.cli`. It reports observed
application/runtime modules, operation-owned TUI modules, public-client
methods, agent modules, and boundary-matrix files. Special CLI spellings such
as `checkout`, `import`, `list`, `pwd`, and lock/unlock use declared discovery
aliases only to find mechanically related modules.

`Observed shape` is intentionally not a closure judgment. The presence of an
application module, public method, or boundary note does not prove authority,
cache, provider, Apply, receipt, or failure-path parity. The separate
[`operation-route-classification.json`](operation-route-classification.json)
is the reviewed input for `curated_state`; the generator validates that it
classifies exactly the canonical Help operation set with no duplicate or stale
names.

The initial curation is deliberately conservative. It marks `CLOSED` only when
a focused matrix or progress-ledger gate says all currently implemented routes
in the stated scope share one terminal-independent application boundary. It
marks `MIXED` when only a lifecycle slice is verified or when recorded evidence
conflicts. Everything else remains `UNREVIEWED`, which is not a euphemism for
`LEGACY`. `LEGACY` requires a trace proving that a command or presentation
module still owns application policy; `N/A` requires an explicit applicability
decision and tests. Missing hypothetical Python, agent, or TUI adapters do not
make an otherwise closed current route mixed.

## Generated artifacts

- [`generated/callable-catalog.jsonl`](generated/callable-catalog.jsonl) is the
  complete symbol-level inventory.
- [`generated/callable-catalog-summary.json`](generated/callable-catalog-summary.json)
  provides small reviewable counts by kind, visibility, and observed route
  shape.
- [`generated/operation-route-catalog.md`](generated/operation-route-catalog.md)
  provides the operation-level entry and layer index.
- [`operation-route-classification.json`](operation-route-classification.json)
  stores the human-reviewed route conclusion and its evidence separately from
  generated source observations.

Run `python scripts/generate_callable_catalog.py` after source changes. Run the
same command with `--check` in verification; the focused test also rejects any
checked-in artifact that differs from a fresh scan.

## Static-analysis boundary

Inbound calls are recorded only when the AST can resolve an exact local,
imported-symbol, imported-module, or `self`/`cls` method target. Dynamic
dispatch, `getattr`, plugin loading, dependency injection, callback values, and
runtime monkeypatching remain unresolved. Static `__all__` values and explicit
package imports determine export evidence; computed exports remain unknown.

These are deliberate limitations, not evidence that an unresolved callable
has no callers. Vertical traces and curated matrices remain authoritative for
runtime effects and architectural completion.

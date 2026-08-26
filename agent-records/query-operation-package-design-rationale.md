# Query operation-package design rationale

Last verified: 2026-08-25.

## Motivation

Query's terminal-independent boundaries had already been extracted, but their
six modules remained flat at the top of `memcommit/`. That was useful while the
boundaries were discovered, yet it made an operation hard to inspect as one
vertical slice and would make the package root grow by two or more modules for
every migrated operation.

## Decision

Query is the first operation grouped under `memcommit.operations`:

```text
memcommit/operations/query/
  ordinary_application.py
  ordinary_runtime.py
  granted_application.py
  granted_source.py
  granted_runtime.py
  reference_application.py
  reference_runtime.py
```

The three routes remain separate because they have different authority and
disclosure contracts. Ordinary Query reads a frozen readable Context set;
granted Query reads concealed Grant material for one process-local response;
`QueryContextRef` authenticates its provider before opening one legacy
concealed Source. Grouping them does not merge those semantics.

Application modules own typed requests, responses, ports, and use-case order.
Runtime modules adapt `MemoryStore`, authority, and persistence. CLI, TUI, and
the existing command compatibility helper import these owners directly.

## Compatibility boundary

The former top-level modules remain as implementation-free identity aliases.
Existing Python callers can therefore keep imports such as
`memcommit.query_application.OrdinaryQueryRequest`, while new repository code
must import the operation package. Importing an old or canonical path in either
order now returns the same canonical module object, not merely the same exported
class and function objects. Pre-relocation pickle globals continue to resolve
through the old paths.

This deliberately removes a separate compatibility-module namespace: module
introspection reports the canonical owner, and a monkeypatch made through an
old path affects that same owner. Query had no internal consumers of the old
paths, so the alias change does not reroute production execution. The ordinary,
granted, and reference modules remain distinct because module identity does not
merge their readable-Context, Grant, and concealed-Source contracts.

Keeping those exports was chosen over an immediate breaking move because the
Python API is not yet versioned and downstream use is not fully inventoried.
Leaving the implementation flat was rejected because it would preserve the
very package-root sprawl this slice is intended to test. A horizontal global
`application/` and `runtime/` split was also rejected: it makes one operation
span multiple distant trees and is harder to review operation by operation.

## Invariants and non-goals

- Provider ordering, authority checks, Source freezing, typed results, and
  output remain owned by the operation. Query has no publication or durable
  effect.
- Application modules still do not import terminal, command, Store, or concrete
  provider implementations; Store integration remains runtime-owned.
- Internal adapters do not route through the top-level compatibility exports.
- CLI and TUI files were intentionally not relocated in the package commit.
  That follow-up is now complete: `query-cli-interface-design-rationale.md` and
  `query-tui-interface-design-rationale.md` record the sibling adapters, while
  `query-callable-boundary-matrix.md` classifies the remaining command-owned
  composition functions.
- Shared Query infrastructure such as provider policy and answer/reference
  helpers stays shared until its ownership is evaluated; this change does not
  move files merely because their names contain `query`.

## Verification

The ordinary, granted, reference, provider, and workbench tests exercise the
same behavior through the new owners. A focused package test checks module
identity in both import orders, old-path pickle loading, lazy package import,
the absence of compatibility-file behavior, and that internal Python modules
do not import the old paths.

This is a path and ownership change only, so it introduces no new interactive
state and requires no replacement TUI screenshot set.

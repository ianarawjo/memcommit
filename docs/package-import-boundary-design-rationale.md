# Package import and operation assembly boundary

Last reviewed: 2026-08-15.

## Motivation

Typed, terminal-independent application functions do not by themselves define
Python package loading. The root package eagerly re-exported the public API,
and the public client eagerly imported every operation integration. Importing
an unrelated `memcommit.*` submodule therefore assembled Add, Query, and Meld
before any operation was selected.

This is package coupling, not a semantic dependency among those operations.
It can make one broken or unavailable integration prevent an unrelated module
from importing, and it makes the effective library boundary unpredictable for
an embedding host. Import isolation is therefore tracked separately from the
application, authority, cache, receipt, CAS, and presentation contracts.

## Selected boundary

Existing public spellings and the single-client model remain compatible:

```python
from memcommit import MemCommitClient

client = MemCommitClient(root="...")
client.add_memories(["One Memory"])
```

The package now observes four boundaries:

```text
memcommit package root
  -> lightweight core exports and lazy public re-exports

public API package
  -> stable names and DTO/error contracts, resolved on demand

MemCommitClient
  -> one frozen Store/provider configuration boundary
  -> operation integrations loaded only when a method selects them

operation adapters
  -> application/runtime use cases
  -> an optional integration may depend inward on an operation, never reverse it
```

`memcommit.__init__` and `memcommit.api.__init__` retain `__all__`, object
identity, and import spellings through module-level lazy attribute resolution.
The first access caches the real object; no proxy type crosses the API.

`MemCommitClient` remains one facade because separate public clients would
change the embedding contract without changing operation semantics. Shared
core values and immutable public result/error types may load with the client,
but Add, Query, and Meld application/runtime assembly is method-selected.
Existing module-level test and host injection points remain patchable: a lazy
loader fills only an unbound sentinel and does not overwrite a value installed
before first use.

The Typer registry remains the console compatibility root. Lazy command
registration is a separate migration because changing it here would mix Help
and command-discovery compatibility with the Python library boundary.

## `IMPORT-01` invariants

1. Importing `memcommit` performs no Store/Profile/provider/terminal I/O and
   does not import the public client until a public client export is accessed.
2. Importing an operation's domain/application/runtime module does not require
   an unrelated operation adapter.
3. Importing or constructing `MemCommitClient` does not assemble Add, Query,
   or Meld implementations merely because their methods exist.
4. Calling a method may load that operation's application/runtime integration.
5. Existing root/API names, `__all__`, and resolved object identity remain
   compatible; public proxy classes are forbidden.
6. One unavailable optional integration must not prevent unrelated standalone
   modules from importing.
7. Installed-wheel verification must run outside the source checkout so an
   editable import cannot conceal a missing file or different graph.

The strict first public audit covers Query, Add, and Meld. Atomize, Update, and
Distill receive the common root and standalone-import checks without gaining a
new public Python contract in this change. Each later public slice inherits the
same gate.

## Alternatives considered

- Removing root exports would shrink imports but break documented usage.
- One client per operation would expose assembly details to callers and split
  the frozen Store/Profile boundary.
- Accepting eager imports because one wheel contains every module would retain
  unnecessary failure coupling.
- Converting Typer registration here would widen a library-boundary change into
  console behavior and Help compatibility.

The selected design keeps the distribution whole while making operation
assembly selective.

## Verification evidence

Five fresh-process tests prove lazy root/API exports, public object identity,
Ground-blocked internal standalone imports, implementation absence after
client import, and Add-only loading without Query or Meld. Existing public
Add, Query, and Meld suites retain their monkeypatch seams and behavior. The
invalid-HOME explicit-root regression continues to prove that import and an
explicit client root do not resolve unrelated Profile state.

A fresh `0.0.1` wheel was installed into a new Python 3.13.5 environment. From
outside the checkout, its root and client imports preserved the same lazy graph
and resolved from `site-packages`. The gate must be repeated for each operation
that later becomes a public slice. The eager Typer console registry remains an
explicit follow-up rather than a hidden exception to this result.

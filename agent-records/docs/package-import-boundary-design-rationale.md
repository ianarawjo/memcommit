# Package import and operation assembly boundary

Last reviewed: 2026-08-26.

## Motivation

MemCommit's application rebuilding established typed, terminal-independent use
cases and sibling CLI, TUI, Python, and agent projections. That dependency
direction did not by itself define Python package loading. The root package
eagerly re-exported the public API, and the public client eagerly imported each
operation integration. Consequently, importing an unrelated submodule first
loaded the complete public client and, after the Distill and Makemore public
slice was assembled, the Ground adapters as well.

This is not a semantic dependency from Distill, Makemore, Update, or Atomize
to Ground. Their application modules do not import Ground. It is a package
assembly dependency created before an operation has been selected. In the
single complete wheel it normally remains invisible, but an import failure in
one integration can prevent an unrelated operation from loading, and a future
embedding host cannot choose a narrow library boundary reliably.

Import isolation is therefore a separate completion axis from application and
terminal isolation. An operation may retain its verified authority, cache,
receipt, CAS, and presentation behavior while its package-import gate remains
pending.

## Selected boundary

The existing public names and one-client usage remain compatible:

```python
from memcommit import MemCommitClient

client = MemCommitClient(root="...")
client.distill_context("examples")
client.distill_ground("ticker-ground")
```

Compatibility does not require eager assembly. The package uses four distinct
boundaries:

```text
memcommit package root
  -> lightweight core exports and lazy public re-exports

public API package
  -> stable names and value contracts, resolved on demand

MemCommitClient
  -> one frozen Store/provider configuration boundary
  -> operation integrations imported only by the selected method

operation adapters
  -> application/runtime use cases
  -> optional Ground integration imports the operation, never the reverse
```

The canonical checkout now places that package below `src/memcommit`. The
distribution name, import name, public exports, and `mem` entry point remain
`memcommit`; only the repository source location changed. A
repository root is deliberately not an import root, so development and CI
must install the project—normally with an editable install—before running the
test suite. This makes the installation boundary the ordinary local path
instead of relying only on a later release smoke test.

Source-backed screenshot reproduction is a deliberate exception: those
scripts put the checkout's exact `src` directory on `PYTHONPATH` so an ordered
historical capture can exercise the intended worktree. That is reproducibility
scaffolding, not distribution evidence. Installed-wheel checks continue to run
outside the checkout because an editable installation can still conceal wheel
contents or package-data omissions.

`memcommit.__init__` and `memcommit.adapters.python_api.__init__` retain `__all__`, object
identity, and documented import spellings through module-level lazy attribute
resolution. A first access caches the real object in that module. No proxy
class or duplicate implementation crosses the public boundary.

`MemCommitClient` remains one public facade. Splitting it into several public
client classes would change the embedding contract without improving the
operation semantics. Its implementation may use local imports or private
operation modules so constructing the client does not select every operation.
Public result and error value modules may load with the facade because they
are bounded contracts with no Store, provider, terminal, or operation effect.
Private application-result annotations in those DTOs are type-checking-only;
they must not pull an application implementation into the runtime import
graph. Existing module-level injection points remain patchable: the lazy
assembly fills only an unbound sentinel and does not overwrite a host or test
double installed before first use.

The CLI keeps its existing command and option names, including Ground forms.
The Typer command registry remains the current console compatibility root in
this slice. Lazy registration of all visible commands is a separate console
entrypoint migration: changing it together with the Python package boundary
would mix `--help` and command-discovery compatibility with library import
isolation.

## `IMPORT-01` invariants

1. Importing `memcommit` performs no Store/Profile/provider/terminal I/O and
   does not import the public client until a public client export is accessed.
2. Importing one operation's domain, application, or runtime module does not
   require an unrelated operation adapter.
3. Importing or constructing `MemCommitClient` does not import Ground,
   Distill, Makemore, Add, Meld, or Query implementation modules merely
   because their methods exist.
4. Calling an operation method may load that operation's application/runtime
   integration. A Ground-specific method may additionally load its exact
   Ground adapter.
5. Ground adapters may depend on the operation application. The operation
   application and standalone runtime must not depend on a Ground adapter.
6. Existing root and `memcommit.adapters.python_api` export spellings, `__all__`, and resolved
   object identity remain compatible. Import isolation must not be achieved
   with public proxy types.
7. Import failure or deliberate unavailability of one optional operation
   integration does not prevent unrelated completed standalone slices from
   importing.
8. The installed wheel is tested from outside the source checkout so editable
   imports cannot conceal missing package files or a different import graph.

Shared core and infrastructure values are not treated as unrelated operation
integrations. `Context`, `Memory`, the frozen `MemoryStore` type, public error
classes, and immutable public result types may be common dependencies so long
as importing them has no external effect. This boundary prevents premature
operation assembly; it does not require one wheel per operation.

## Completed-slice audit

The first strict audit covers Query, Add, Meld, Distill, and Makemore because
they are the completed public Python/agent slices. Summarize, Atomize, Update,
and other internal slices receive the common package-root and application
import checks, but this change does not publish a new Python or agent contract
for them. Remaining operations are characterized and inherit `IMPORT-01` when
their public vertical slice is completed.

Existing application, runtime, authority, cache, receipt, effect, and TUI
verification is not reopened unless the import change alters its production
path. `IMPORT-01` is reported independently rather than retroactively claiming
that an earlier semantic boundary was invalid.

The later internal Switch slice applies the same inward dependency direction
without publishing a Python or agent surface. `switch_application.py` and
`switch_runtime.py` import no command or terminal adapter; the Switch TUI
depends on the typed request and neutral Context picker; and Ground imports the
neutral picker rather than the Switch command. The eager Typer registry still
loads the command adapter at console assembly, which remains the separate
entrypoint migration described above.

## Alternatives considered

- **Remove root-level public exports.** This would make the package root small
  but break the documented Query/Add API for no semantic benefit. Lazy real
  exports preserve the contract.
- **Publish one client class per operation.** This makes assembly visible to
  callers and complicates one frozen Store/Profile boundary. The selected
  design keeps one facade and narrows its internal imports.
- **Split Ground into new user-visible command and agent tool names.** Ground
  integration can be isolated without changing those contracts. A later
  product decision may split discovery surfaces, but import topology alone
  does not justify it.
- **Convert the complete Typer registry in the same change.** Command
  registration has separate Help and entrypoint compatibility. It remains a
  recorded follow-up after the library boundary is verified.
- **Accept eager imports because every module ships in one wheel.** This would
  preserve unnecessary failure coupling and make the application boundary
  weaker for embedding hosts. A complete distribution and selective assembly
  are compatible goals.
- **Keep the flat checkout and rely only on installed-wheel CI.** That can be
  correct, but it lets ordinary local `pytest` runs import the adjacent source
  package without exercising project installation. The `src` layout makes the
  safer boundary the default while retaining the independent wheel gate.

## Verification gate

`IMPORT-01` passed its first strict gate on 2026-08-15. Five fresh-process tests
prove lazy root/API exports, public object identity, Ground-blocked standalone
imports, operation implementation absence after client import, and selected
Makemore loading without Ground, Distill, or Meld assembly. The earlier
invalid-HOME explicit-root test continues to prove absence of import-time
Profile resolution. A focused public API and agent registry
run passed 112 tests.

A fresh `0.0.1` wheel was then installed with its former MCP extra into a new
Python 3.13.5 environment. From outside the checkout, official MCP 2.0.0 stdio
discovered Query, Add, Meld, Distill, Makemore, and Fit, executed Add, and
returned the typed unknown-tool failure. A second installed-process check
proved the same lazy import graph from `site-packages`. This closes the first
public-slice import gate; the Typer console registry remains a separately
recorded migration rather than a hidden exception to this result.

The 2026-08-26 source-layout migration added a checked `package-dir`/discovery
contract and moved all 1,035 tracked package files below `src/memcommit`.
Only the static catalog's repository scan and two repository-backed Study
fixture locators required production-code path changes; import spellings and
entry points did not change. The package/import, generated-catalog, fixture,
and ownership regression set passed 571 tests, and the former MCP projection set
passed 16 tests. All migrated capture and support scripts also passed Python
compilation and their generated-layout checks.

A wheel built from a clean temporary source copy contained exactly the same
1,010 Python modules as `src/memcommit`, retained the declared assets and eval
fixtures, and contained no `src`, test, or documentation tree. Installing that
wheel into a separate environment outside the checkout loaded `memcommit` from
`site-packages`; `mem --help`, one Store write/read round trip, and packaged
font lookup succeeded. A wheel built in the existing dirty checkout reproduced
the already documented stale-root-`build/` hazard, so clean-source wheel
construction remains a required release boundary rather than being weakened
by the `src` migration.

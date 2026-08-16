# Package import and operation assembly boundary

Last reviewed: 2026-08-15.

## Motivation

MemCommit's application rebuilding established typed, terminal-independent use
cases and sibling CLI, TUI, Python, and agent projections. That dependency
direction did not by itself define Python package loading. The root package
eagerly re-exported the public API, and the public client eagerly imported each
operation integration. Consequently, importing an unrelated submodule first
loaded the complete public client and, after the Distill and Elaborate public
slice was assembled, the Ground adapters as well.

This is not a semantic dependency from Distill, Elaborate, Update, or Atomize
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

`memcommit.__init__` and `memcommit.api.__init__` retain `__all__`, object
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
   Distill, Elaborate, Add, Meld, or Query implementation modules merely
   because their methods exist.
4. Calling an operation method may load that operation's application/runtime
   integration. A Ground-specific method may additionally load its exact
   Ground adapter.
5. Ground adapters may depend on the operation application. The operation
   application and standalone runtime must not depend on a Ground adapter.
6. Existing root and `memcommit.api` export spellings, `__all__`, and resolved
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

The first strict audit covers Query, Add, Meld, Distill, and Elaborate because
they are the completed public Python/agent slices. Summarize, Atomize, Update,
and other internal slices receive the common package-root and application
import checks, but this change does not publish a new Python or agent contract
for them. Remaining operations are characterized and inherit `IMPORT-01` when
their public vertical slice is completed.

Existing application, runtime, authority, cache, receipt, effect, and TUI
verification is not reopened unless the import change alters its production
path. `IMPORT-01` is reported independently rather than retroactively claiming
that an earlier semantic boundary was invalid.

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

## Verification gate

`IMPORT-01` passed its first strict gate on 2026-08-15. Five fresh-process tests
prove lazy root/API exports, public object identity, Ground-blocked standalone
imports, operation implementation absence after client import, and selected
Elaborate loading without Ground, Distill, or Meld assembly. The earlier
invalid-HOME explicit-root test continues to prove absence of import-time
Profile resolution. A focused public API, agent registry, and MCP projection
run passed 112 tests.

A fresh `0.0.1` wheel was then installed with its MCP extra into a new Python
3.13.5 environment. From outside the checkout, official MCP 2.0.0 stdio
discovered Query, Add, Meld, Distill, Elaborate, and Fit, executed Add, and
returned the typed unknown-tool failure. A second installed-process check
proved the same lazy import graph from `site-packages`. This closes the first
public-slice import gate; the Typer console registry remains a separately
recorded migration rather than a hidden exception to this result.

# Query plain CLI interface boundary

Last reviewed: 2026-08-22.

## Decision

Non-interactive selector parsing and terminal rendering live in
`memcommit.interfaces.cli.query`. `memcommit.commands.query` remains the Typer
composition root: it interprets options, freezes storage/authority inputs,
chooses ordinary, granted, or legacy-reference execution, wires concrete
providers, and maps failures to exit codes.

The CLI adapter owns exact opaque-handle splitting, ordinary answer rendering,
opaque Query View catalogs, and terminal-safe granted/reference answers. It
does not import `MemoryStore`, provider connectors, command modules, or
application runtimes. It cannot open a Context, broaden a Grant, connect a
provider, select a route, or persist a result.

There are no transcript list/detail renderers. `mem query` has no session
flags, and the application result types contain no session receipt.

## Invariants

- Omitted selectors open the TUI only when stdin and stdout are TTYs.
- Ungrounded ordinary answers retain their explicit label.
- Query View catalogs expose only opaque handles and Flow Circular
  placeholders, never source text.
- Answer content crosses the shared safe-terminal transformation.
- The command passes only completed typed results to renderers; presentation
  never reconstructs authority or execution policy.

## Alternatives considered

Moving the Typer callback into `interfaces.cli` was rejected because authority
attachment recovery, Context loading, provider construction, progress, and
exit policy are composition rather than presentation. Returning one formatted
string from application code was rejected because catalog and answer outcomes
remain useful typed values for TUI, Python, and agent adapters.

The command's historical positional grammar remains at the executable edge.
The public Python and agent interfaces use three explicit routes and do not
copy that ambiguity.

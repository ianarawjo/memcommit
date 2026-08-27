# Query plain CLI interface boundary

Last reviewed: 2026-08-26.

## Decision

Non-interactive selector parsing and terminal rendering live in
`memcommit.adapters.interfaces.cli.query`. `memcommit.adapters.console.commands.query.command` remains the Typer
composition root: it interprets options, freezes storage/authority inputs,
chooses ordinary, granted, or legacy-reference execution, wires concrete
providers, and maps failures to exit codes.

The CLI adapter owns ordinary, granted, and legacy-reference answer rendering.
It does not import `MemoryStore`, provider connectors, command modules, or
application runtimes. It cannot open a Context, broaden a Grant, connect a
provider, select a route, or persist a result. Memory-handle parsing and Query
View catalog rendering were removed with that feature.

For the first positional value, the command composition resolves an accessible
target before using the historical question fallback:

1. an exact local or READ-granted existing Context resolves through the shared
   current-Context snapshot and locator rules;
2. an exact public QUERY route resolves independently through typed Grant
   metadata;
3. a matched target plus `QUESTION` runs one-shot, while a matched target
   without `QUESTION` opens that target in the TUI when a terminal is present;
4. only an unmatched single bare value falls back to a question over the
   current ordinary Context.

Relative locators, authority failures, and a selector followed by a second
positional question never fall back. A name available through both READ and
QUERY is rejected as ambiguous; `--context/-c` selects the readable route.
Repeated `-c` remains the explicit multi-Context form, and the historical
single QUERY-only `-c` alias remains compatible. `-d` and `-r` continue to mean
ordinary direct/recursive reach or exact/federated reach for a Query View.

There are no transcript list/detail renderers. `mem query` has no session
flags, and the application result types contain no session receipt.

## Invariants

- Omitted selectors open the TUI only when stdin and stdout are TTYs.
- Ungrounded ordinary answers retain their explicit label.
- Answer content crosses the shared safe-terminal transformation.
- The command passes only completed typed results to renderers; presentation
  never reconstructs authority or execution policy.

## Alternatives considered

Moving the Typer callback into `interfaces.cli` was rejected because authority
attachment recovery, Context loading, provider construction, progress, and
exit policy are composition rather than presentation. Returning one formatted
string from application code was rejected because the three answer routes
remain distinct typed values for TUI, Python, and agent adapters.

The fallback intentionally makes an unmatched one-word value a question today
but a target if an accessible Context with that exact name is created later.
This instability is accepted because single-word natural-language questions
are not a primary use case; callers that require stable meaning use `-c`, `.`,
or the explicit Python/agent routes. The public Python and agent interfaces do
not copy this CLI ambiguity.

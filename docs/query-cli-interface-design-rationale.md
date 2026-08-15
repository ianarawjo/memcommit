# Query plain CLI interface boundary

## Decision

Query's non-interactive selector parsing and terminal rendering live in
`memcommit.interfaces.cli.query`. `memcommit.commands.query` remains the Typer
composition root: it interprets public options, freezes storage and authority
inputs, chooses the ordinary, granted, or legacy-reference application route,
connects progress/provider/runtime adapters, and maps failures to exit codes.

Last reviewed: 2026-08-15.

## Motivation

Before this extraction, the command mixed four concerns in one file:

1. Typer's public command grammar and route overloads;
2. storage, Grant, provider, and application composition;
3. opaque `VIEW#HANDLE` selector parsing;
4. plain terminal presentation for answers, catalogs, and saved transcripts.

The application/runtime packages and full-screen TUI can already run without
Typer, but the plain output contract was still command-owned. That made it hard
to review whether a future Python or agent adapter reused semantic execution or
accidentally copied console behavior along with it.

## Boundary and invariants

The CLI adapter owns only these projections:

- exact `#q-xxxxxxxxxxxx` handle splitting;
- ordinary grounded and explicitly ungrounded answer rendering;
- opaque query-view catalogs whose placeholders never expose source text;
- task-owned saved-session lists and visible transcript details;
- legacy reference answers and granted answers through terminal-safe text.

It imports typed operation responses and transcript/catalog models, but it does
not import `MemoryStore`, provider connectors, command modules, or application
runtimes. It cannot open a Context, broaden a Grant, connect a provider, publish
a session, or select an execution route. The command passes only a completed
typed result into it.

Terminal capability detection now uses the shared
`interfaces.console.terminal.is_interactive_terminal` boundary. This preserves
the existing rule that omitted selectors may open the Query TUI only when both
stdin and stdout are TTYs, while removing Query's duplicate direct dependency
on process streams.

The adapter preserves existing output text and escaping. In particular, an
ungrounded ordinary answer retains its bold first-line label, a query catalog
retains opaque Flow Circular placeholders, and answer/transcript content passes
through the established safe terminal transformation.

## Alternatives considered

Moving all of `commands.query.cmd` into `interfaces.cli` was rejected. Route
selection includes authority attachment recovery, Context loading, progress,
provider construction, session publication, and exit-code policy; treating
that orchestration as presentation would reverse the desired dependency
direction.

Returning one preformatted string from the application layer was also rejected.
Catalogs, answers, and transcripts are different typed outcomes, and retaining
those types lets the TUI, CLI, Python, and future agent adapters project them
without parsing terminal text.

## Remaining boundary

`commands.query` is still the executable composition root and is intentionally
large because the public `mem query` syntax overloads ordinary questions,
opaque query views, legacy references, sessions, and the no-argument TUI route.
A later bootstrap/router extraction may turn that route choice into a typed
request, but it must preserve the existing authority checks, provider timing,
session CAS boundary, and error/exit behavior. This change does not create the
agent adapter or a new public Python facade.

# Help application design rationale

## Motivation

Study feedback identified operation discovery as an entry-point problem: a
person or agent should be able to learn what an operation means, when to use
it, and whether it is deterministic or semantic without reading command
implementation files. MemCommit already had one audited 59-operation catalog
and a substantial CLI/TUI browser, but only terminal presentation consumed the
catalog as a complete operation. Python and agent callers had no equivalent
stable discovery route.

The missing boundary was therefore not another prose source. It was one
terminal-independent `list`/`describe` use case over the existing source.

## Contract

`memcommit.help_application` owns two read-only application actions:

- `list_operation_help()` returns one immutable alphabetized snapshot of all
  public operations;
- `describe_operation(name)` returns the exact catalog record for one public
  operation and rejects blank, padded, case-changed, or unknown names.

Each record retains the existing stable fields: name, summary, flow, execution
kind, effect, range, and best-use situation. The application boundary imports
only `help_catalog`. It does not initialize or inspect a Store, resolve a
Profile, connect a provider, read authority, use a cache, create a session, or
publish a receipt.

## Interface projections

The CLI/TUI Help inventory takes one application snapshot and then combines it
with interface-owned command forms and categories. Typer registration still
uses each catalog summary as static command metadata; this is interface
assembly, not a second Help execution path. Wide/compact layout, grouping,
focus, syntax forms, and shell-selection behavior remain owned by the terminal
adapter.

`MemCommitClient.list_operations()` and
`MemCommitClient.describe_operation()` project the same records to immutable
public DTOs. They deliberately do not touch the client's frozen Store or
provider dependencies.

The version-1 `memcommit_help` agent tool exposes `list` and `describe`. It is
registered first as the discovery entry point and projects unchanged through
the existing MCP registry. Successful replies always report `effect: NONE`.
The tool describes operations but never invokes them, grants authority, or
claims that a runtime cache/provider/Apply path is available.

## Why this design

Keeping the catalog as the only semantic source prevents CLI, TUI, Python, and
agent descriptions from drifting. A separate application query makes the
route callable and testable without moving presentation details into the
catalog. Exact names keep discovery deterministic and make unknown operations
fail visibly instead of guessing an alias.

The alternative of scraping Click/Typer help was rejected because registered
syntax is interface-specific and cannot faithfully express execution kind,
effect, range, or best-use meaning. Duplicating those fields in the MCP schema
or an agent skill was rejected because every wording correction would then
require synchronized edits in multiple semantic sources.

## Boundaries and non-goals

- Exact CLI flags, parser defaults, aliases, and forms remain interface-owned.
- Runtime authority, provider, cache, receipt, and Apply outcomes belong to the
  invoked operation and are not predicted by Help.
- Detailed algorithms and design rationale remain in operation documentation.
- This change does not revise the 59 English descriptions or the existing TUI
  layout. Human English/Korean wording review remains a separate catalog task.
- An agent skill may teach a workflow around `memcommit_help`, but the skill is
  not another executable or semantic source.

Because the terminal presentation is unchanged, this boundary extraction does
not require a replacement TUI screenshot set.

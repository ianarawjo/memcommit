# Help application design rationale

## Motivation

Study feedback identified operation discovery as an entry-point problem: a
person or agent should be able to learn what an operation means, when to use
it, and whether it is deterministic or semantic without reading command
implementation files. MemCommit already had one audited 62-operation catalog
and a substantial CLI/TUI browser, but only terminal presentation consumed the
catalog as a complete operation. Python and agent callers had no equivalent
stable discovery route.

The missing boundary was therefore not another prose source. It was a
terminal-independent operation and detail query over the existing source.

## Contract

`memcommit.help_application` owns four read-only application actions:

- `list_operation_help()` returns one immutable alphabetized snapshot of all
  public operations;
- `describe_operation(name)` returns the exact catalog record for one public
  operation and rejects blank, padded, case-changed, or unknown names;
- `list_operation_details(name)` returns compact typed detail references for
  one exact operation; and
- `describe_operation_detail(name, detail_id)` returns one exact complete
  comparison, limitation, access boundary, or semantic boundary by its stable
  operation-local ID.

Each record retains name, summary, flow, execution kind, effect, range, and the
reviewed use situation. `use_when` is the public discovery name for the
existing `best_for` value, which remains as a compatibility field. An operation
may also carry structured detailed comparisons: one title and explanation plus
named alternatives with guidance. These comparisons cover adjacent operation
selection, invocation routes, deterministic behavior cases, materialization
routes, and closed verdict examples. Typed prose details cover limitations and
access boundaries without turning every caveat into an unclassified note.
Each detail has a stable operation-local ID, discovery role, and use situation;
an optional one-line discovery summary is required when an agent needs the
detail before choosing a tool. The application boundary imports only
`help_catalog`. It does not initialize or inspect a Store, resolve a Profile,
connect a provider, read authority, use a cache, create a session, or publish a
receipt.

## Interface projections

The CLI/TUI Help inventory takes one application snapshot and then combines it
with interface-owned command forms and categories. Typer registration still
uses each catalog summary as static command metadata; this is interface
assembly, not a second Help execution path. Wide/compact layout, grouping,
focus, syntax forms, and shell-selection behavior remain owned by the terminal
adapter. The terminal chooses how to render a comparison, but not its meaning.

`MemCommitClient.list_operations()`, `describe_operation()`,
`list_operation_details()`, and `describe_operation_detail()` project the same
records to immutable public DTOs. Operation records carry compact detail
references; a full comparison or prose body is loaded only by its exact detail
query. These methods deliberately do not touch the client's frozen Store or
provider dependencies.

The version-1 `memcommit_help` agent tool exposes `list`, `describe`,
`list-details`, and `describe-detail`, with explicit `use_when` and typed detail
references. It is registered first as the discovery entry point and projects
unchanged through the existing MCP registry.
Every registered execution tool also carries compact use-when and detail
reference metadata. MCP appends `use_when` and only `TOOL_SELECTION` discovery
summaries to its description for hosts that expose only standard fields. It
also publishes `memcommit/useWhen` and `memcommit/helpDetails` in `_meta` so a
caller can request the full payload by exact operation/detail ID. `ON_DEMAND`
bodies do not consume every tool's initial description. Successful
Help replies always report `effect: NONE`. Help never invokes another
operation, grants authority, or predicts a runtime cache/provider/Apply path.

Companion Skills put their selection trigger in the required frontmatter
description. Their bodies may name a stable detail ID and retain its immediate
procedural consequence, but they do not redefine the full detail or replace
Help.

## Why this design

Keeping the catalog as the only semantic source prevents CLI, TUI, Python, and
agent descriptions from drifting. A separate application query makes the
route callable and testable without moving presentation details into the
catalog. Exact names keep discovery deterministic and make unknown operations
fail visibly instead of guessing an alias.

The alternative of scraping Click/Typer help was rejected because registered
syntax is interface-specific and cannot faithfully express execution kind,
effect, range, use-when, or detailed comparison meaning. A generic free-form
`notes` field was rejected because callers could not distinguish a selection
boundary from syntax, warning, rationale, or implementation commentary.
Structured comparisons and typed prose details instead preserve the decision
shape and boundary kind across interfaces. Per-operation modules under
`help_catalog/details/` keep growing content reviewable without turning the
main operation catalog into a long mixed-purpose file; one explicit registry
checks ownership and duplicate IDs. MCP and Skills project only what their
discovery contracts need; neither is a second semantic source.

## Boundaries and non-goals

- Exact CLI flags, parser defaults, aliases, and forms remain interface-owned.
- Runtime authority, provider, cache, receipt, and Apply outcomes belong to the
  invoked operation and are not predicted by Help.
- Detailed algorithms and design rationale remain in operation documentation.
- Human English/Korean wording review remains a separate catalog task.
- An agent Skill is host guidance, not another executable or semantic source.

The first maturity and typed-prose presentation is recorded at both `180×52`
and `100×30` under
`docs/screenshots/mem-help-import-query-details-20260816/`.
The later operation-wording review and its structured Merge, Atomize, Distill,
Translate, Impact, Fit, and Conformance details are recorded under
`docs/screenshots/mem-help-reviewed-content-20260816/`.
The final category review adds typed Log, Revert, Profile, Provider, and legacy
Eval route details. Eval's tag and detail describe the current fixed research
harness without changing its separate operation-route classification.

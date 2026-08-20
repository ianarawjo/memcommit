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

Later study discussion identified a second discovery gap: a participant may
know the intended action without knowing an operation name. Showing the whole
inventory in response can expose substantially more operation guidance than
the participant requested. Natural-language lookup therefore selects a small
catalog subset but does not generate substitute Help prose.

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

`memcommit.help_lookup_application` owns that bounded semantic selection. It
freezes the complete public catalog, treats the request and catalog as
untrusted provider data, and accepts only an ordered array of zero to three
exact operation names. Each candidate exposes the model to the canonical
summary, best-for, flow, execution, effect, range, maturity, and only
tool-selection detail summaries. The model never returns descriptions,
reasons, scores, forms, or commands. An empty array is the closed no-match
result. Unknown, duplicate, over-limit, explanatory, or malformed output fails
the complete turn without publishing partial rows.

The complete compact catalog is one frozen `TOP_K_RERANK` frame. The current
adapter supports only one-shot execution; if the catalog ever exceeds the
shared provider-input bound, lookup rejects it instead of prefiltering or
silently omitting operations. The terminal validates and freezes this plan
before connecting the pinned `gpt-5.6-sol` provider with reasoning effort
`none`. The lookup application receives that provider through a protocol and
does not resolve a Profile, open a Store, read Memory content, create a
session, or execute the selected operations.

## Interface projections

The CLI/TUI Help inventory takes one application snapshot and then combines it
with interface-owned command forms and categories. Typer registration still
uses each catalog summary as static command metadata; this is interface
assembly, not a second Help execution path. Wide/compact layout, grouping,
focus, syntax forms, and shell-selection behavior remain owned by the terminal
adapter. The terminal chooses how to render a comparison, but not its meaning.

When a positional request is supplied, `mem help REQUEST` bypasses the full
browser, performs one lookup, and renders each selected operation through the
same collapsed command-row projection already used by interactive Help. Each
row contains only `mem NAME`, the canonical summary, and canonical `WHEN`
(`best_for`) text. Results retain provider order, are not numbered or scored,
and the command exits after rendering. A no-match result prints one fixed
interface-owned message. Bare `mem help`, shell selection, exact Python/agent
Help, and MCP discovery retain their existing deterministic behavior and do
not connect a provider.

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

Restricting the semantic model to ID selection also protects study exposure.
Generated `WHY` prose, adjacent alternatives, confidence scores, and complete
operation details were rejected because they teach more of the operation model
than the requested compact answer. Returning several direct matches remains
necessary for requests containing several actions, but every match receives
the same fixed two-part Help row and the hard maximum remains three.

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
- Natural-language lookup does not promise that a selected operation is ready
  for particular operands, authority, provider state, or Apply conditions.
- Natural-language lookup is currently a CLI projection; exact Python, agent,
  and MCP Help contracts remain version 1 and provider-free.

The first maturity and typed-prose presentation is recorded at both `180×52`
and `100×30` under
`docs/screenshots/mem-help-import-query-details-20260816/`.
The later operation-wording review and its structured Merge, Atomize, Distill,
Translate, Impact, Fit, and Conformance details are recorded under
`docs/screenshots/mem-help-reviewed-content-20260816/`.
The final category review adds typed Log, Revert, Profile, Provider, and legacy
Eval route details. Eval's tag and detail describe the current fixed research
harness without changing its separate operation-route classification.

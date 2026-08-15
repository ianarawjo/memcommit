# Query public Python API design rationale

Last verified: 2026-08-15.

## Motivation

Query already had three terminal-independent application/runtime pairs, but a
Python caller still had to import internal requests, construct a Store and
readable catalog, choose a provider connector, classify command-era
exceptions, and decide whether a granted session publication was part of the
call. That was reusable implementation, not yet a stable library contract.

The public boundary must let CLI, agent adapters, and Python callers use
the same operation meaning without exposing command routing or freezing
internal dataclasses as a permanent ABI.

## Public surface

`memcommit.api.MemCommitClient` and its result, configuration, and error types
are also re-exported from `memcommit`. The first bounded surface deliberately
contains three explicit methods:

```python
client.query_ordinary(question, context_names=...)
client.query_granted(public_name, question, session_name=...)
client.query_reference(reference, question)
```

There is no overloaded public `query()` router in this version. The CLI's
positional grammar has historical ambiguity between an ordinary question, a
public granted route, and a legacy reference. Reproducing that ambiguity in a
library would make errors and authority less predictable. The agent adapter
maps a versioned tagged schema to these three methods without reimplementing
their policies, as recorded in
`query-agent-adapter-design-rationale.md`.

## Store and lifecycle ownership

A client freezes exactly one Store root at construction:

- `root=...` selects an explicit local-only Store boundary;
- `profile=...` selects one visible registered Profile without changing the
  process-global active Profile;
- omitting both snapshots the active Profile and its Store root;
- supplying both is rejected;
- `create=False` is the default, so constructing a read client does not create
  Store directories or `state.json`.

The client has no `close()` contract. Providers are connected per operation
call and the client retains no endpoint, terminal, or background task. Its
`QueryProviderConfig` is an immutable snapshot of non-secret model, reasoning,
and timeout settings. The defaults preserve the evaluated Query Sol/none
policy and 600-second timeout. Supplying a different snapshot is explicit and
does not mutate the user's CLI configuration.

An injected provider factory is supported for tests and embedding hosts. The
same source-before-provider or provider-before-source ordering remains owned
by the internal application use case; injection cannot bypass those gates.

## Operation invariants

### Ordinary Query

Every Context operand is resolved from one captured current-Context snapshot.
The client freezes the Profile-readable catalog, then delegates to
`execute_ordinary_query`. READ authority and the complete whole-frame preflight
finish before provider construction. The public result contains the exact
plain answer text used by the CLI plus typed citations. No cache, session,
receipt, or durable mutation is added by the facade.

An explicit `root` client is local-only. It cannot inherit a host Profile's
grants merely because a local Context happens to share an attachment name.

### Granted Query

Granted Query remains active-Profile scoped because the authority registry,
Grant snapshot lock, concealed Source resolution, and session Store currently
share that process-level boundary. A client bound to an explicit root or a
non-active Profile fails with `QueryAuthorityError` before provider
construction. This is an intentional limitation, not silent fallback.

The public method keeps the internal read/publication split but presents one
high-level success contract. Without `session_name`, it returns only a
revalidated catalog or answer. With `session_name`, successful return means the
turn was separately reauthorized for `SESSION_LOG`, the Source was rechecked,
and the transcript was CAS-published. A publication failure raises
`QueryPublicationError`; the method never returns an answer-shaped partial
success. The internal unpublished publication token is not public API.

Only opaque catalog handles and placeholder lines cross the facade. Concealed
authority content and internal freshness tokens do not.

### QueryContextRef

The legacy reference method accepts the existing durable `QueryContextRef`
value because that value is already part of serialized Context data. It
constructs/authenticates the routed provider before opening the exact concealed
Source UID/name/language and never publishes a session.

## Stable result and error projection

Public results copy the minimum durable meaning from internal values:

- `OrdinaryQueryResult` with `QueryCitation` values;
- `GrantedQueryResult` in `CATALOG` or `ANSWER` mode, optionally with a
  `QuerySessionReceipt`;
- `ReferenceQueryResult`.

Internal request, response, publication-token, and authority-source classes
remain free to evolve. Public callers catch the `MemCommitError` / `QueryError`
hierarchy rather than Typer exits or implementation-specific exceptions:

- `QueryInputError` for invalid caller values;
- `QueryConfigurationError` for client/provider configuration;
- `QueryContextError` for unavailable Contexts or Sources;
- `QueryAuthorityError` for Profile or Grant failures;
- `QueryProviderFailure` for endpoint construction/completion failures;
- `QueryExecutionError` for a failed authorized semantic run;
- `QueryPublicationError` for the separate granted-session commit boundary;
- `QueryStorageError` for local I/O failures.

Every projected exception retains its internal cause with exception chaining.
Provider factories are wrapped at their exact construction boundary so a
generic connection `RuntimeError` is not misclassified as semantic execution.

## Infrastructure ownership

The evaluated Find/Query provider connector now lives at
`memcommit.infrastructure.providers.find_query`. Public API code imports that
owner directly. Find and Query commands also import it directly; the former
`commands.find_query_provider_policy` and
`commands.ordinary_query_provider_policy` modules are implementation-free
compatibility exports only. This keeps endpoint authentication, connection
logging, timeout injection, and model selection outside interfaces while
retaining one production policy.

## Verification and limits

Focused tests prove:

- root-level and `memcommit.api` exports are identical;
- read-client construction does not create a missing Store;
- ordinary Query returns typed citations and preserves all Source files;
- relative Context operands share one current snapshot;
- reference provider construction precedes concealed Source opening;
- granted high-level success includes the exact session receipt and stores no
  concealed Source content;
- publication failure yields no partial public success;
- explicit roots do not inherit host grants;
- public API modules import neither commands nor terminal frameworks; and
- provider-policy compatibility exports retain object identity; and
- an exact-tree `uv build --wheel` artifact contains both new packages and
  imports the same root/API objects from an isolated virtual environment.

This change does not expose Find, Add, Sever, or Summarize, add async or
cancellation semantics, provide an MCP/network tool host, make granted reads
portable across non-active Profiles, or promise internal request dataclasses as
public API. The separate agent adapter is a thin versioned projection over this
facade rather than another application implementation.

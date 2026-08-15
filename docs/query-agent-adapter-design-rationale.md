# Query agent adapter design rationale

Last verified: 2026-08-15.

## Motivation

The public Query Python facade made operation behavior callable without a
terminal, but an agent host still needed a bounded machine contract. Letting
each host infer CLI positional routing or serialize internal application values
would reproduce ambiguity, authority decisions, and publication policy outside
MemCommit.

The first agent boundary therefore maps one tagged JSON request to exactly one
public `MemCommitClient` method. It does not add another Query implementation.

## Contract

`memcommit.interfaces.agent.query.QueryAgentAdapter` accepts a JSON-compatible
object with `version: 1` and one explicit `kind`:

- `ordinary` maps to `MemCommitClient.query_ordinary`;
- `granted` maps to `MemCommitClient.query_granted`;
- `reference` reconstructs the durable public `QueryContextRef` routing value
  and maps to `MemCommitClient.query_reference`.

`query_agent_tool_schema()` returns a fresh function-tool schema named
`memcommit_query`. Its three `oneOf` branches reject unknown fields and keep
the operation route visible. The schema is a host registration value, not a
provider prompt and not an authorization grant.

There is deliberately no selector guessing. An ordinary question cannot be
reinterpreted as a granted public route, and a granted name cannot silently
fall back to ordinary Context content. The host or skill selects the route
from user intent and available public control-plane metadata.

## Result projection

Every response is JSON-safe and retains the same version and route:

```json
{
  "version": 1,
  "ok": true,
  "kind": "ordinary",
  "result": {}
}
```

Ordinary results preserve the public answer, grounded flag, and typed
citations. Granted results preserve `CATALOG` versus `ANSWER`, opaque catalog
handles/placeholders, and the optional completed `QuerySessionReceipt`.
Reference results preserve only the public Source name and answer. Internal
requests, authority Sources, publication tokens, Store objects, providers, and
exception causes never enter the machine result.

The granted-session invariant is inherited rather than reconstructed: when a
request includes `session_name`, an `ok: true` result can contain a receipt only
after the public client has completed its separate `SESSION_LOG`/Source/CAS
publication. A failed publication returns an error and no answer-shaped partial
success.

## Errors and disclosure

Invalid JSON shape fails before the public client. Public exception categories
map to stable codes:

| Public category | Agent code | Detail policy |
| --- | --- | --- |
| input | `invalid_request` | bounded validation detail |
| configuration | `configuration_error` | public configuration detail |
| Context/Source | `context_unavailable` | public locator detail |
| authority | `authority_denied` | public authority detail |
| provider | `provider_failure` | fixed redacted message |
| execution | `execution_failed` | fixed redacted message |
| publication | `publication_failed` | fixed redacted message |
| storage | `storage_failure` | fixed redacted message |
| unexpected implementation failure | `internal_error` | fixed redacted message |

Provider error bodies, host filesystem paths, internal exception text, and
concealed Source content are not diagnostic output for an agent. Only provider
failure is marked retryable. Publication is not automatically retryable because
the host must not assume that repeating a semantic call or write is harmless.
Every error message is stripped of control characters and capped at 1,000
characters, including validation text derived from caller-supplied field names.

## Dependency and host boundary

The adapter imports the stable public API and the already-durable
`QueryContextRef` type. It imports no command, operation/runtime module,
infrastructure connector, Store implementation, Typer, or prompt-toolkit code.
The embedding host constructs the `MemCommitClient`, chooses its Store/Profile
and provider configuration, then may pass it to the default in-process registry
that freezes this schema and dispatches a payload to `QueryAgentAdapter.invoke`.

Neither layer is an MCP server, network listener, subprocess protocol, or
automatic plugin registration. Those are deployment adapters that may wrap the
registry. Keeping them separate allows an in-process agent host, MCP server, or
other tool runtime to share the same schema and result behavior.

## Skill boundary

The companion skill is intentionally procedural and thin. It tells an agent
how to choose an explicit route, preserve version 1, avoid inventing Context or
reference metadata, interpret success/error values, and treat a granted
publication failure as no returned answer. The skill does not run the CLI,
connect to a provider, inspect concealed data, or reproduce the JSON schema.
Its canonical source lives at `skills/memcommit-query/` and passes the skill
validator. A wheel does not install it into a user's agent environment;
plugin/skill installation and external host exposure remain a later
distribution boundary.

## Verification and non-goals

Focused tests prove schema freshness and route coverage, exact argument mapping
for all three public methods, catalog and publication receipt preservation,
strict request rejection before client use, JSON serialization, every public
error-code mapping, sensitive-detail redaction, the dependency direction, and
the skill's required route/version/failure instructions.

This version does not provide streaming, cancellation, batch calls, automatic
retry, transcript listing, dynamic tool discovery, an overloaded router, or a
cross-Profile granted authority service. Changing request or result meaning
requires a new contract version; adding an optional field still requires tests
and a documented compatibility decision.

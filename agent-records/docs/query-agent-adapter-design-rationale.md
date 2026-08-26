# Query agent adapter design rationale

Last verified: 2026-08-26.

## Contract

`QueryAgentAdapter` maps one tagged JSON request to exactly one public
`MemCommitClient` method. Contract version 3 has three strict kinds:

- `ordinary` -> `query_ordinary`;
- `granted` -> `query_granted`; and
- `reference` -> `query_reference` using supplied durable reference metadata.

Version 3 requires `question` for granted Query and removes `memory_handle`,
CATALOG results, and catalog fields. This is an intentional contract change
rather than silently accepting fields that no longer have an effect.
`query_agent_tool_schema()` returns a fresh version-3 function schema whose
branches reject unknown fields.

There is no route guessing. An ordinary question cannot be reinterpreted as a
Query View, and a granted public name cannot fall back to readable Context
content.

## Result and error projection

Every response is JSON-safe and retains version, route, and `ok`. Ordinary
results preserve answer, grounded state, and typed citations. Granted results
preserve the public View name and one answer. Reference results preserve only
public Source name and answer. Internal
requests, concealed Sources, Store objects, providers, and exception causes do
not enter the result.

Public errors map to stable input, configuration, Context, authority, provider,
execution, storage, and internal codes. Provider/error bodies, filesystem
paths, concealed Source text, and unexpected implementation details are
redacted. Only provider failure is retryable; retry policy must not imply that
repeating a semantic turn is harmless.

## Dependency and skill boundary

The adapter imports the public API and durable `QueryContextRef`, not command,
operation/runtime, provider connector, Store, Typer, or prompt-toolkit modules.
An embedding host owns client construction and dispatch.

The companion `skills/memcommit-query` instructions require version 3,
explicit route selection, and one-shot result handling. They do not run the
CLI, inspect concealed content, reproduce the JSON schema, or promise
transcript retention.

## Non-goals

The adapter provides no streaming, cancellation, batching, automatic retry,
transcript listing, dynamic tool discovery, overloaded router, or cross-Profile
granted authority service. Changing request or result meaning requires a new
contract version.

## Verification

Focused tests cover version-3 schema freshness, exact mapping for all routes,
required granted questions, absence of catalog/session fields, strict rejection before
client use, JSON serialization, public error-code mapping, sensitive-detail
redaction, dependency direction, and skill version/route instructions.

# MCP registry projection design rationale

Last verified: 2026-08-15.

## Motivation

The in-process agent registry exposes function-tool schemas with `parameters`
and returns complete versioned JSON envelopes. MCP calls the corresponding
schema field `inputSchema` and represents a tool result as both content and an
optional structured object. This vocabulary translation must be explicit, but
it must not make authority, retry, or operation decisions.

`McpRegistryProjection` is the SDK-independent seam between those contracts.
Keeping it free of the MCP Python package lets the core wheel, CLI, tests, and
other in-process hosts import the projection without starting a transport or
accepting an SDK version dependency.

## Discovery projection

Construction snapshots the already-frozen registry discovery list and requires
each schema to have a matching nonblank name, nonblank description, and
JSON-safe object-valued `parameters`. Registration order must match projection
order. Each `list_tools()` call returns fresh `McpToolDefinition` values:

- `name` remains unchanged;
- `description` remains unchanged; and
- `parameters` becomes `inputSchema` without changing the schema body.

The projection stores canonical JSON rather than caller-owned dictionaries, so
mutating one discovery response cannot change later discovery or the registry.
Nested object keys must be text and non-finite numbers are rejected.

## Call projection

`call_tool(name, arguments)` forwards one already-decoded argument object to
`AgentToolRegistry.invoke`. The complete registry response is preserved twice:

- canonical compact JSON in `content_text` for a human-readable MCP content
  block; and
- the decoded object in `structured_content` for machine consumers.

`is_error` is true unless the registry envelope has `ok: true`. The projection
does not raise operation failures, rewrite their messages, or convert Add into
a retryable call. Unknown tools remain the registry's bounded, non-retryable,
zero-effect error. An MCP SDK adapter must build its result from these three
values rather than interpreting the operation again.

## Verification and next boundary

Focused tests prove exact Query/Add schema translation, discovery isolation,
successful structured/text parity, unchanged operation and registry failures,
startup failure for malformed schemas, nested-key rejection, and the absence
of SDK, terminal, Store, provider, or operation-runtime imports.

This commit does not install the MCP SDK, create protocol objects, open stdio,
register a console entrypoint, parse JSON-RPC, or choose Store/Profile/provider
configuration. The next layer binds this projection to the stable v2 MCP Python
SDK while keeping that dependency optional.

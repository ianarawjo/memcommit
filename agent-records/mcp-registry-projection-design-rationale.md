# MCP registry projection design rationale

Last verified: 2026-08-16.

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

Construction snapshots the already-frozen registry discovery definitions. Each
definition contains one standard tool schema with a matching nonblank name,
nonblank description, and JSON-safe object-valued `parameters`, plus a separate
optional nonblank `use_when` and immutable typed Help-detail references.
Registration order must match projection order.
Each `list_tools()` call returns fresh `McpToolDefinition` values:

- `name` remains unchanged;
- `description` remains unchanged when no trigger exists, or gains one explicit
  `Use when:` paragraph when it does; bounded summaries from details classified
  `TOOL_SELECTION` follow as selection boundaries, while `ON_DEMAND` detail
  bodies stay out of initial prose;
- `use_when` is also projected to namespaced `memcommit/useWhen` metadata;
- every compact detail reference is projected to
  `memcommit/helpDetails`, including its exact operation, ID, kind, use
  situation, discovery role, and optional discovery summary; and
- `parameters` becomes `inputSchema` without changing the schema body.

The duplicated visibility is deliberate. MCP hosts reliably show the standard
description but may not surface custom metadata; machine consumers that retain
metadata can read the trigger and discover exact detail IDs without parsing
prose. Full comparisons, limitations, and access boundaries remain structured
results of `memcommit_help` with `kind: describe-detail` rather than being
copied into every execution tool or its input schema.

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

Focused tests prove exact Query/Add/Meld/Atomize Grounding/Distill/Elaborate/Fit
schema translation, use-when and typed-detail description/metadata preservation
through both the SDK-independent projection and an official-v2 in-memory
client, selective Add/Query summary exposure, discovery isolation, successful
structured/text parity, unchanged operation and registry failures, startup
failure for malformed schemas, nested-key rejection, and the absence of SDK,
terminal, Store, provider, or operation-runtime imports.

The projection still does not own the MCP SDK, stdio, JSON-RPC, or
Store/Profile/provider configuration. A separate optional v2 SDK server binds
these values to `mem-mcp`; adding a registry tool therefore reaches MCP without
adding a second operation handler.

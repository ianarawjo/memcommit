# MCP stdio server design rationale

Last verified: 2026-08-15.

## Motivation

The in-process agent registry already exposes the reviewed Query and Add
contracts, but an external MCP host cannot call a Python object directly. It
needs a protocol transport that preserves those contracts without rebuilding
operation policy inside a second command implementation.

`mem-mcp` is the first such transport. It runs one official MCP Python SDK v2
server over stdio and projects the process-frozen registry created at startup.
The SDK is an optional `mcp` installation extra so ordinary Python and `mem`
CLI consumers do not acquire an unused protocol dependency.

## Boundary and data flow

```text
MCP host
  -> official SDK stdio transport
  -> MCP registry projection
  -> frozen AgentToolRegistry
  -> public MemCommitClient
  -> reviewed Query or Add application boundary
```

The transport owns MCP initialization, discovery objects, decoded call
dispatch, and protocol result objects. It does not own authority, Context
resolution, provider policy, cache decisions, receipts, retries, or mutation.
Those remain behind the same public client and application functions used by
the Python and agent interfaces.

Every registry response is returned twice in one MCP result: canonical JSON
text for clients that consume content blocks, and the same decoded object as
`structuredContent`. A response whose public envelope does not contain
`ok: true` sets `isError`, but its error code, message, retryability, and receipt
remain unchanged. Unknown tool calls therefore keep the registry's bounded,
non-retryable, zero-effect error instead of leaking an internal exception.

## Process configuration

The server freezes one `MemCommitClient` at process start. It accepts either an
explicit existing Store root or one configured Profile, never both. Optional
model, reasoning-effort, and timeout flags produce one immutable Query provider
configuration snapshot. The server does not create a Store and does not infer
one from an MCP request.

Tool handlers run in a worker thread because current Store and provider ports
are synchronous. The wait is deliberately non-abandoning: cancellation does
not let the protocol task forget an Add while its durable mutation may still be
running. No partial result is published before that call returns.

Stdout is reserved for the MCP stdio stream. Startup and configuration failures
go to stderr and return a nonzero exit code.

## Alternatives and limits

- A second set of MCP-specific Query/Add handlers was rejected because it would
  duplicate validation, authority, and receipt semantics.
- The high-level SDK server was not required for two already frozen dynamic
  registry entries. The v2 low-level server directly accepts discovery and call
  callbacks and keeps the adapter small.
- MCP SDK v1 was rejected because it entered maintenance when v2 became the
  current stable line. The optional dependency is bounded to major version 2 so
  a future incompatible major cannot silently alter the transport contract.
- HTTP transport, remote authentication, dynamic tool registration, server-side
  protocol retries, and MCP resources or prompts are intentional non-goals.
- This layer does not make the repository's tracked `build/lib` tree
  authoritative. A standard build can still reuse stale copied modules; the
  installed-wheel verification must exclude that derived tree until the wider
  packaging work removes or isolates it.

## Verification

Focused tests use the official v2 client and in-memory transport to initialize
the server, discover its exact schema, call a successful tool, and observe an
unknown-tool error. Separate checks prove text/structured parity, the optional
entry-point metadata, startup validation, and the absence of command, TUI,
operation, infrastructure, or Store imports from the transport adapter.

The installed-wheel check is recorded separately in
`mcp-installed-wheel-verification.md`. It uses an isolated environment and the
real stdio entry point to prove discovery, one durable Add checkpoint, bounded
unknown-tool failure, and source-checkout independence.

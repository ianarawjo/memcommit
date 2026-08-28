# Agent adapter ownership and MCP retirement design rationale

Last reviewed: 2026-08-27.

## Decision

`memcommit.adapters.agent` is the canonical owner of MemCommit's host-neutral,
machine-callable JSON tool contracts. The former
`memcommit.adapters.interfaces.agent` staging package moved here without a
compatibility facade.

MemCommit no longer ships an MCP transport. The `mem-mcp` console entry point,
the optional MCP SDK dependency, the SDK-independent projection, the stdio
server, and their transport-specific tests were removed together. Historical
MCP verification records remain as dated evidence, not current support claims.

## Motivation

The agent registry is used directly by tests and can be embedded by an
in-process host, while the MCP layer had no repository-owned consumer beyond
its own entry point and tests. It also repeated schema freezing, JSON safety,
discovery isolation, and result-envelope checks already owned by
`AgentToolRegistry`. Its installed smoke still expected an older eighteen-tool
catalog while the current registry exposes twenty-five tools, demonstrating a
support surface that had drifted ahead of a concrete use case.

Keeping the speculative transport would make protocol compatibility and an
optional SDK part of the distribution contract without a current product
purpose. Retiring it makes the maintained boundary match the behavior that is
actually exercised.

## Preserved contract

- Operation adapters retain strict versioned request parsing and JSON result
  envelopes.
- `AgentToolRegistry` remains the frozen discovery and dispatch boundary over
  one caller-owned `MemCommitClient`.
- Tool selection guidance, typed Help references, and host-neutral effect hints
  remain in `AgentToolDefinition`.
- Registry discovery returns fresh values, invocation validates JSON safety,
  and unknown or failed calls return bounded public errors.
- `contract.py` stays below operation adapters, while `registry.py` composes
  those adapters above it; this avoids a registry/adapter import cycle.

The package root is an import-light marker. Registry composition types come
from `memcommit.adapters.agent.registry`, while operation-specific adapters,
schemas, and names come from their owning modules; importing one operation does
not assemble the complete default registry.

## Alternatives and remaining boundary

Moving only MCP beneath `adapters.agent` was rejected because it would leave
the actual agent contracts under the temporary `adapters.interfaces` owner.
Keeping the full MCP projection as a dormant compatibility surface was rejected
because no external import compatibility had been promised and the transport
duplicated registry guarantees. A thin MCP module can be added later if a real
host integration requires it, but that work must choose and test its protocol
version, lifecycle, authentication, cancellation, packaging, and installed
artifact boundary at that time.

MemCommit currently provides no MCP discovery, stdio server, or other standard
wire transport. An embedding host must call `AgentToolRegistry` in process or
provide its own adapter over the frozen definitions and invocation envelope.

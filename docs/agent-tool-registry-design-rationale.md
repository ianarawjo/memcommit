# Agent tool registry design rationale

Last verified: 2026-08-16.

## Motivation

Query and Add first supplied strict schemas and adapters, but a host still had
to assemble them independently. Compare, Update, Meld, structural Atomize,
Atomize Grounding, Distill, Elaborate, Fit, Forget, and Resolve now use that
same path rather than introducing operation-specific MCP handlers. The
integration path covers tool
discovery, name dispatch, shared client ownership, JSON-safe output, and the
transition from one durable mutation to a later read through the same process.

`memcommit.interfaces.agent.registry` is the host-neutral in-process connection
point. It makes shipped tools discoverable and callable without importing the
CLI or TUI and without choosing a wire protocol.

## Frozen host contract

`build_default_agent_tool_registry(client)` binds the twenty currently shipped
tools, from Help and direct inspection through deterministic and semantic
operations, to one caller-owned `MemCommitClient`. The client has
already frozen its Store/Profile root and provider configuration; the registry
does not reconstruct or widen those choices.

Each `AgentToolBinding` contains a public tool name, schema factory, handler,
use-when guidance, and immutable compact Help-detail references. One-to-one
operation bindings obtain the latter two through the public Help API rather
than importing catalog internals. At registry construction, every binding is
checked for:

- a nonblank unique name;
- callable schema and handler values;
- a schema name equal to the binding name;
- recursively text-only JSON object keys; and
- finite, JSON-safe schema values;
- nonblank use-when guidance; and
- a typed tuple of uniquely identified detail references.

The schema is serialized once into a canonical process-local snapshot.
Discovery returns a newly decoded object every time, so callers cannot mutate
the registered contract and a stateful schema factory cannot change a running
host. Registration order is retained for deterministic discovery.

## Dispatch and effect boundary

`AgentToolRegistry.invoke(name, payload)` accepts an already-decoded payload.
For a known tool it invokes exactly one frozen handler. Every adapter then
performs strict versioned parsing and calls exactly one public client
method. The registry adds no route inference, authority, provider, cache,
receipt, retry, or persistence policy.

Known operation responses pass through after recursive text-key and strict JSON
serialization checks. An invalid or unknown tool name returns a bounded
non-retryable registry error without opening the Store. A handler exception,
non-object result, non-finite value, or non-text nested key becomes one redacted
`internal_error`; host paths and custom exception bodies are not disclosed.
Operation-level results and errors retain their own version and `kind`.
Registry-level errors use registry version 1 and `kind: null` because no
operation contract was entered.

| Callable | Input → output | Effects | Invariant |
| --- | --- | --- | --- |
| `AgentToolRegistry.__init__` | bindings → frozen registry | schema factories once | duplicate/malformed contracts fail before host start |
| `tool_schemas` | none → fresh schema objects | none | frozen order and content; caller mutation is isolated |
| `invoke` | tool name + decoded payload → JSON object | exactly the selected adapter's effects | unknown names have no effects; every result is JSON-safe |
| `build_default_agent_tool_registry` | public client → shipped tool registry | none at construction | one shared frozen client; no terminal dependency |

## MCP and transport boundary

The shipped function-tool schemas retain the standard `name`, `description`,
and `parameters` shape. A registry discovery definition pairs that unchanged
schema with separate `use_when` and `help_details` slots. One-to-one operation
bindings take both from the public Help facade; composite tools supply one
reviewed composite trigger and only details they actually own. Registration
rejects blank guidance, disagreement between a schema factory and its binding,
untyped detail containers, or duplicate detail IDs; it freezes all three
values. A concrete MCP adapter projects `parameters` to MCP `inputSchema`,
selectively exposes the guidance and compact detail references, decodes
arguments, calls `registry.invoke`, and encodes the returned object.
Authentication, stdio or HTTP lifecycle, MCP capability negotiation,
cancellation, and transport error codes belong to that adapter.

Keeping this translation outside the registry means an in-process agent,
MCP server, test harness, or another tool runtime shares the same frozen
operation contracts. It also prevents an MCP dependency from becoming a
requirement for the Python library or CLI.

## Verification and limitations

Focused tests verify schema and Help-discovery freezing, fresh discovery,
duplicate and invalid registration rejection, unknown-name zero effects,
result redaction, JSON safety, and terminal-free imports. The principal
integration test invokes Add
through the registry into a real Store, verifies the exact three-Memory batch
and one checkpoint, then invokes ordinary Query through the same registry and
public client. Query observes both the newly added Memories and the ordinary
checkpoint evidence while leaving the post-Add Store byte-for-byte unchanged.

Grounding integration tests project all five lifecycle actions, call one
provider-free real saved dialogue through MCP, and preserve typed issue,
question, proposal, and Apply receipt data. Separate semantic integration tests
invoke Distill and Elaborate through the
same registry and MCP projection, verify typed evidence and verification
fields, and prove that neither read-only tool creates a Context or accepts a
proposal.

The earlier clean-wheel check covered Query/Add discovery and a real Add
invocation. On 2026-08-16 a fresh current-worktree wheel exposed all fifteen
then-current tools and executed Help, Show, a real Add, a saved Grounding `open`,
structural Atomize saved `open`/Apply/retry, and Forget's provider-free
empty-Source Analyze/no-op Apply/replay through the official stdio client
outside the checkout. The current registry contains twenty tools; this is a
source-tree discovery assertion rather than a new installed-wheel claim.
Provider-backed semantic execution remains in-process evidence. The registry
is not a plugin, network endpoint, authentication service, Skill installer,
idempotency service, or dynamic runtime registry. Adding shipped operations
remains an explicit code and compatibility change.

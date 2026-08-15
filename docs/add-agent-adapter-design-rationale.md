# Add agent adapter design rationale

Last verified: 2026-08-15.

## Motivation

The public Add facade already owns input validation, target resolution,
CREATE authority, target CAS, exact ordered persistence, and the single
checkpoint receipt. An agent host still needs a bounded machine contract. If
each host parsed its own payload or called CLI intake modes, it could silently
rewrite text, lose duplicates, misreport partial success, or retry a mutation
whose first receipt was merely delayed.

`AddAgentAdapter` is therefore a projection over
`MemCommitClient.add_memories`, not a second Add implementation. It imports no
command, TUI, Store, operation, or provider module.

## Version 1 request contract

The registered tool name is `memcommit_add_memories`. Its strict object has:

- `version: 1`;
- `kind: "memories"`;
- a nonempty `contents` list of nonblank strings; and
- optional `context_name`, which may be omitted only to use the public
  client's frozen current-Context behavior.

Unknown fields and other versions fail before the public client is called.
Each list item is one exact Memory. Order, duplicates, whitespace, punctuation,
and embedded newlines are retained. The schema intentionally does not declare
`uniqueItems`. One invocation maps to one public method call and therefore one
successful Add checkpoint.

The adapter does not accept file paths, paste instructions, argv fragments,
TUI drafts, provider prompts, provenance overrides, new Context identifiers,
or caller-selected authority. Those concerns belong to other interfaces or to
the public runtime boundary.

## Success and failure envelopes

A success envelope returns the canonical Context name and UID, the ordered
created Memory UID/content pairs, the count, and the single checkpoint UID.
The adapter reports success only after the public method returns this complete
receipt. It does not claim that Add created or switched a Context, ran a
provider, or saved a review session.

Failures use the shared versioned agent envelope and a bounded, control-safe
message. Caller-correctable input, missing-Context, and authority messages may
retain their public exception text. Conflict, storage, execution, generic Add,
and unexpected failures use stable redacted messages so host paths and
implementation details do not cross the tool boundary.

Every version-1 Add failure has `retryable: false`. Add mutates durable state
and has no idempotency key or status endpoint, so a missing or delayed receipt
does not prove that another invocation is safe. A future retryable mutation
contract requires an explicit idempotency and receipt-lookup design rather than
reclassifying an exception.

## Shared agent mechanics and skill boundary

Query and Add share only generic JSON-object validation and bounded error
envelope construction in `memcommit.interfaces.agent.contract`. Their routes,
schemas, result serialization, error categories, and retry rules remain
operation-owned. In particular, Query may retry one provider failure while Add
never advertises an automatic retry.

`skills/memcommit-add/` is checked-in host guidance. It directs an agent to the
registered tool, preserves exact-batch meaning, requires durable user intent,
and forbids hidden CLI or filesystem fallback. The skill is not automatically
installed and is not included in the Python wheel. The default in-process agent
registry now binds this adapter and schema to a caller-owned public client;
external host exposure and skill installation remain explicit deployment
responsibilities.

## Verification and non-goals

Focused tests cover strict schema/version parsing, validation before the public
call, exact multiline/duplicate/order transfer, one-call receipt serialization,
stable error categories, no mutation retry, error redaction and bounds,
dependency direction, and the companion skill contract. Query adapter tests
also run after extraction of the shared envelope mechanics.

This slice does not add an MCP server, network endpoint, Codex plugin, process
transport, authentication layer, idempotency key, dry run, status lookup,
context creation, or skill installer. The shared in-process registry can expose
the returned schema and invoke the adapter, but a transport must not broaden
its authority or reinterpret an absent receipt as success.

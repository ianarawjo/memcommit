# Query public Python API design rationale

Last verified: 2026-08-26.

## Public surface

`memcommit.adapters.python_api.MemCommitClient`, its result/configuration/error types, and the
same root-package exports provide three explicit one-shot methods:

```python
client.query_ordinary(question, context_names=...)
client.query_granted(public_name, question)
client.query_reference(reference, question)
```

There is no overloaded `query()` router and no session argument. The CLI's
historical selector grammar is unsuitable as a library authority contract.

## Store and lifecycle ownership

A client freezes one Store root at construction. Explicit `root` is local-only;
`profile` selects a registered Profile without changing the process-global
active Profile; omitting both snapshots the active Profile. Read-client
construction does not create missing Store state.

Providers connect per operation. `QueryProviderConfig` is an immutable
non-secret model/reasoning/timeout snapshot, and an injected factory supports
tests or embedding hosts without bypassing application ordering.

## Operation invariants

Ordinary Query resolves every operand from one captured current-Context
snapshot, freezes the Profile-readable catalog, and completes READ authority
and whole-frame preflight before provider construction. The result contains
the CLI answer text and typed citations. It creates no cache, receipt, or
durable mutation.

Granted Query remains active-Profile scoped because its Grant lock and
concealed Source resolution use that process boundary. A nonblank question is
required and it returns one revalidated answer. There is no per-Memory catalog
or selector, publication token, session
receipt, or partial-success publication failure. Concealed Source content and
freshness tokens never cross the facade.

The legacy reference method accepts a durable `QueryContextRef`,
constructs/authenticates its routed provider before opening the exact
concealed Source, and returns one answer without persistence.

## Stable result and error projection

- `OrdinaryQueryResult` includes `QueryCitation` values.
- `GrantedQueryResult` contains the public View name and answer.
- `ReferenceQueryResult` contains the public Source name and answer.

Public callers catch `MemCommitError` / `QueryError` categories for input,
configuration, Context/Source, authority, provider, execution, and storage
failures. `QueryPublicationError` and `QuerySessionReceipt` were removed with
the retention feature. Projected errors retain their internal cause through
exception chaining, while provider-factory failures are classified at their
exact construction boundary.

## Compatibility and limits

Legacy Profile values containing `SESSION_LOG` normalize to `QUERY` before
the API resolves authority. This is configuration compatibility only; it does
not make legacy transcript records callable.

The API does not expose async/cancellation, a network tool host, a convenience
router, or granted reads bound to a non-active Profile. Internal application
dataclasses remain free to evolve independently from the public result types.

## Verification

Tests cover identical root/API exports, no-write client construction, typed
ordinary citations, one current-locator snapshot, provider-before-Source
reference ordering, granted answer projection without a receipt,
explicit-root grant isolation, stable public error mapping, and dependency
direction away from commands and terminal frameworks.

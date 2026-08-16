# Structural Atomize agent tool design rationale

Last reviewed: 2026-08-15.

## Motivation

The structural Atomize public API exposes a complete analysis and exact in-place
Apply, but an MCP process cannot retain the private Python proposal object from
one request to the next. Reconstructing that object in the transport adapter or
accepting only public IDs would create a second application policy and weaken
the stale-review boundary.

`memcommit_atomize` therefore projects two deliberately small version-1
actions over `MemCommitClient`:

- `open` calls `open_atomize_analysis` and returns the complete visible
  proposal, cache/provider origin, effect classification, and opaque version;
- `apply_as_is` calls `apply_saved_atomize_as_is` with that exact 64-character
  version and returns the checkpoint and source-to-result lineage receipt.

Save As, workbench response editing, and provider-backed reanalysis of an
edited review remain outside this tool. They need separate reviewed contracts
rather than transport-owned shortcuts.

## Cache, provider, and effect contract

`open` retains the existing operation policy. `SAVED` and `EXACT_PREWARM` set
`cache_used: true`; only `PROVIDER` sets `provider_used: true`. A saved open has
`effect: NONE`, while provider and exact-prewarm materialization report
`effect: DERIVED_SESSION`. None of these paths edits the selected Context.

`refresh: true` explicitly requests a new provider analysis and dominates the
prepared-cache preference. `use_prepared: false` disables only hidden prepared
reuse, not an exact saved-session hit. These controls are strict booleans and
the response exposes the actual origin so an agent need not infer what ran.

`apply_as_is` never constructs a provider and reports
`effect: CONTEXT_CHECKPOINT`. Its action name, exact reviewed version, and
explicit Context form the final machine request; there is no separate boolean
that could be accidentally detached from the action being approved.

## Stateless exact-version boundary

The public `apply_saved_atomize_as_is` entry loads the saved analysis/workbench
under the ordinary session lock. It accepts only:

1. the current exact version; or
2. after a successful Apply whose response may have been lost, the exact
   preterminal version obtained by removing only that terminal application
   receipt and verifying its digest.

The second case recovers the already committed checkpoint. Any different
response, Output plan, layout, analysis, or workbench edit is a stale conflict.
This makes retry safe across MCP process restarts without a process-local
proposal cache and without broadening acceptance to a merely similar review.
The existing application runtime still rechecks Source digest and performs the
single checkpoint/receipt mutation.

## Adapter and transport boundary

The adapter imports only the stable public API and the shared agent-envelope
contract. Each valid action calls exactly one public client method. Invalid
versions, fields, or booleans stop before Store access. Provider and internal
errors are bounded and redacted; public input and missing-Context errors retain
their actionable messages, while stale state is a non-retryable `stale_state`
requiring a new `open`.

The frozen agent registry places structural Atomize immediately before the
separate conversational `memcommit_atomize_grounding` tool. MCP projects the
same schema and result without importing commands, TUI code, Store internals,
or Atomize runtimes into the transport adapter.

## Companion Skill boundary

`skills/memcommit-atomize/` is checked-in host guidance rather than another
operation implementation. It directs an agent to the registered tool, keeps
saved/prepared/provider origin distinct, requires the complete returned
proposal to be shown before mutation, and copies the exact reviewed version
into `apply_as_is`. It permits one byte-for-byte Apply retry only when the
transport response was lost, because that exact revision has a recovery
contract; a typed stale or operation failure is not an invitation to retry.

The Skill does not run the CLI, read the Store, emulate Save As, edit review
responses, or redirect conversational issue resolution away from the separate
Grounding tool. It is a distributable source artifact, not evidence that a
particular agent host has installed the Skill or registered the MCP tool.

## Verification and limits

Focused tests cover strict parsing, complete JSON projection, cache/provider
and effect fields, error redaction, one-public-call ownership, adapter import
isolation, registry/MCP discovery, provider-backed first open, saved second
open, exact Apply, transport retry recovery, stale-version rejection, one
provider call, one checkpoint, and the companion Skill's review, cache,
version, retry, and no-fallback instructions. The Skill also passes the
canonical Skill Creator structural validator.

A fresh installed wheel is also exercised from outside the checkout through
the official MCP stdio client. The smoke opens a pre-created saved structural
review without a provider, applies its exact version, retries it, and verifies
the resulting two Memories and single checkpoint through an independent Store
read. This is package and local-transport evidence, not a claim about remote
authentication, native Windows behavior, or the excluded Save As/editing
lifecycle.

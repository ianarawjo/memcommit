# Forget agent-adapter design rationale

Last reviewed: 2026-08-16.

## Motivation and contract

Forget now has one terminal-independent Analyze, Select, Revise, and Apply
lifecycle, plus a stable Python facade. An agent host still needs a
strict machine-readable route that does not duplicate Source loading,
provider, authority, CAS, or checkpoint policy.

`memcommit_forget` version 1 therefore exposes four explicit actions:

| Action | Required operation values | Effect |
| --- | --- | --- |
| `analyze` | instruction and optional existing Context name | none; freezes and semantically reviews the complete direct Source |
| `select` | review UID, exact expected version, candidate UID, and selection | none; advances one immutable in-memory review |
| `revise` | review UID, exact expected version, and guidance | one provider turn, no Store change; advances the review |
| `apply` | review UID and exact expected version | explicit no-op, or the reviewed Source mutation and one checkpoint |

The adapter calls only `MemCommitClient`. Its JSON projection is not a second
implementation of Forget.

## Process-local retention and exact actions

Forget deliberately has no durable analysis session. The adapter retains at
most 64 current `ForgetReviewResult` values inside one adapter process and
labels every review `PROCESS_LOCAL`. Eviction and process exit make a review
unavailable; callers must Analyze again. The adapter never serializes the
private frozen snapshot or provider dialogue into a portable token.

Select, Revise, and Apply require the opaque version returned by the preceding
action. A stale version fails before provider or Store access. After a version
is applied, it cannot be selected or revised. The adapter retains that exact
Apply receipt while the review remains resident so an identical Apply retry
returns the same checkpoint identity with `recovered: true` and `effect:
NONE`, rather than attempting a second mutation. This is process-local replay
protection, not a durable Forget cache or cross-process idempotency promise.

## Safety and failure boundary

- Request parsing rejects unknown fields and invalid action-specific values
  before calling the public client.
- Analyze, Select, and Revise report `effect: NONE`; a first changed Apply
  reports `SOURCE_CHECKPOINT`; an all-KEEP Apply and an exact retry report
  `NONE`.
- Public authority, provider, stale-Source, storage, and execution failures map
  to bounded typed errors. Provider and internal details are redacted so host
  paths or raw provider bodies do not cross the tool boundary.
- The frozen registry owns discovery and dispatch but no second Forget handler
  or wire-transport policy.

Durable resume, server-shared reviews, hidden prepared-result caching, and
automatic mutation retry are intentional non-goals. Any future durable review
would require an independently reviewed schema, privacy policy, cleanup
lifecycle, and cross-process concurrency contract.

## Verification

Focused tests exercise a real Store and provider fixture across Analyze,
Select, Revise, Apply, stale versions, process replacement, concurrent Source
change, all-KEEP no-op, exact Apply replay, bounded error mapping, schema
freshness and registry discovery. The adapter has an AST gate that permits only
the public API and shared agent-contract dependency, with no command, TUI,
runtime, Store, or wire-transport import.

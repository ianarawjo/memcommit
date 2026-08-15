# Compare shared Endpoint Setup migration rationale

## Status

Compare's new-session A/B selection now uses
`memcommit.interfaces.tui.components.endpoint_setup` through a narrow
operation adapter under `interfaces/tui/operations/compare`.  Explicit
noninteractive Compare operands, saved-session selection, provider analysis,
cache lookup, analysis persistence, and result workbench behavior are not
relocated by this change.

## Motivation

The command-hosted endpoint shell and the rebuilt Endpoint Setup both offered
Context choice, exact-or-descendant reach, and direct-Memory focus.  Keeping
Compare on the former after establishing the latter would preserve two focus
grammars and two stale-Memory clearing implementations.  Compare is the first
real two-readable-endpoint consumer because it exercises independent A/B
scope without an Apply-side mutation boundary.

## Boundary and translation

The command adapter still owns the authority-sensitive work:

- freeze the complete local plus READ-granted public catalog;
- retain exact Grant annotations for display;
- resolve and load only the explicitly selected public Context through its
  effective READ access; and
- project only direct owned Memories as `EndpointSetupMemory` values.

The operation TUI adapter receives that already-frozen catalog and loader.  It
constructs two equal-authority roles, returns one typed process-local
`CompareEndpointSelection`, and performs no provider call or durable write.
The command adapter maps the selection back to the existing
`CompareSetupReceipt`, which continues through the same explicit `cmd(...)`
boundary as command-line operands.

The translation is exact:

| Shared value | Existing Compare input |
| --- | --- |
| A Context | `reference_name` / `from_` |
| B Context | `compared_name` / `to` |
| A descendants | `reference_descendants` |
| B descendants | `compared_descendants` |
| A Memory UID | `reference_memory_uid` / `reference_memory` |
| B Memory UID | `compared_memory_uid` / `compared_memory` |

## Invariants

- A and B remain distinct readable public Contexts.
- A and B retain independent exact-or-descendant reach.
- A and B may each select one direct Memory only while that role is exact.
- Context replacement or descendant broadening clears only the affected
  role's Memory UID before the receipt is constructed.
- Moving a Context cursor does not open its content; explicit selection loads
  and validates that exact readable Context.
- Setup cancellation returns no receipt and cannot connect a provider, create
  an analysis, change current Context, or add a checkpoint.
- The downstream Compare input still owns exact Memory resolution, complete
  Context freshness, saved-analysis matching, Grant combination checks, and
  provider-result validation.  The TUI does not weaken or duplicate them.

## Compatibility and rejected alternatives

The saved comparison schema and cache identity were not moved into the TUI.
The setup receipt is merely another projection of the same explicit command
arguments, so whole-Context defaults remain unchanged and focused requests
continue to match only analyses with the same actionable frames and complete
Context digests.

Adding another compatibility facade around the legacy endpoint shell would
reduce call-site changes but leave its independent focus and rendering state
authoritative.  Reimplementing readable authority inside the new component
would invert the intended dependency and risk treating visibility as
permission.  The selected design keeps authority in the command/application
adapter and interaction mechanics in the shared TUI component.

## Verification and remaining boundary

Component and adapter tests cover unchanged whole-exact defaults, one focused
Memory on each side, an exact A Memory combined with recursive B, typed receipt
translation, READ-granted catalogs, cancellation, and the existing Compare
cache/session/semantic regressions.  Ordered 180×52 PTY evidence records the
actual command adapter from entry through reviewed receipt and cancellation,
including unchanged Store bytes, zero checkpoints, and zero provider calls.

The legacy endpoint shell remains necessary for Atomize, Update, Meld, and
operations that require new-Context editing or mode-dependent roles.  Update
is the next suitable A/B migration once its mutation, session, and Apply
boundaries are held fixed separately.

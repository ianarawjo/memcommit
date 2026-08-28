# Update shared Endpoint Setup migration rationale

## Status

Update's new-session Source/Target selection now uses
`memcommit.adapters.console.tui.components.endpoint_setup` through a narrow adapter
under `interfaces/tui/operations/update`. Explicit noninteractive operands,
provider planning, cache lookup, persisted sessions, and mutation semantics
remain owned by the existing Update modules. The later review-to-Apply phase
order is now composed through the operation-neutral application flow while
Update retains its own CAS, checkpoints, receipt, Undo, and Redo behavior.

## Motivation

Update needs the same visible role grammar already exercised by Compare:
independent Source and Target Context choice, exact-or-descendant reach, and
optional direct-Memory focus. Retaining a second command-hosted implementation
would leave two focus traversals and two stale-Memory clearing rules for the
same interaction contract. Update is also the first migrated consumer whose B
role can mutate, so setup must stop before planning or application authority.

## Boundary and translation

The command adapter continues to own the authority-sensitive work:

- freeze the complete local plus READ-granted public catalog;
- retain exact Grant annotations for display;
- resolve and load only the explicitly selected public Context through its
  effective READ access; and
- project only direct owned Memories as `EndpointSetupMemory` values.

The operation TUI adapter receives that frozen catalog and projection loader.
It returns one typed process-local `UpdateEndpointSelection`, validates that A
and B are distinct, and performs no provider call, session write, cache write,
or Context mutation. The command adapter maps the selection to the existing
Update arguments:

| Shared value | Existing Update input |
| --- | --- |
| A Context | `source_name` / `--from` |
| B Context | `target_name` / `--to` |
| A descendants | `source_descendants` |
| B descendants | `target_descendants` |
| A Memory UID | `source_memory_uid` / `--source-memory` |
| B Memory UID | `target_memory_uid` / `--target-memory` |

Only the new-session setup path changes. A typed receipt re-enters the same
`cmd(...)` boundary as explicit CLI operands, so downstream validation is not
duplicated in the TUI.

The plain command also exposes the shared `-d/--direct` and `-r/--recursive`
presets. They map to both role booleans before the same boundary; the existing
role-specific long flags can still override either side. The persisted scope
continues to store the resolved booleans rather than the spelling used.

## Invariants

- A and B remain distinct readable public Contexts.
- A and B retain independent exact-or-descendant reach.
- Either role may select one direct Memory only while that role is exact.
- Changing a Context or broadening that role to descendants clears only its
  stale Memory UID.
- Moving a Context cursor does not open content; explicit selection loads and
  validates the exact readable Context.
- Target write/accept-derived authority is checked after setup and before a
  provider connection or materialization.
- A focused Source exposes the selected Memory as actionable provenance while
  neighboring Memories remain context-only evidence.
- A focused Target allows edit/remove of only that Memory and exposes no ADD
  target, preventing a sibling result from escaping the reviewed scope.
- The exact selected Memory UIDs and complete observed Source/Target graph
  digests are part of saved-session and exact cache identity.
- Setup cancellation publishes no receipt and cannot connect a provider,
  create a session/cache, change current Context, or add a checkpoint.

## Cache, application, and compatibility boundaries

Whole-Context requests retain the existing exact, equivalent-scope, and
projected Study prewarm lookup. A focused-Memory request can reuse an exact
persisted session or Impact cache only when both selected UIDs and the complete
observed graphs match. It deliberately does not consume a whole-frame
projected prewarm: that cached plan may act on a sibling Memory that the focused
request did not authorize. A future focused projection requires an operation-
aware proof that filters and revalidates every disposition, not a TUI change.

Update session schema 6 remains the emitted form for unchanged whole-Context
sessions. Schema 7 is emitted only when at least one focused UID exists, so old
readers and existing Study receipts retain their prior representation while
focused identity becomes durable. A CLI inline Source emits schema 8 with the
exact process-local Memory and deterministic synthetic identity. It creates no
stored Context; Apply reconstructs that Source and locks only durable target
Contexts. The setup TUI remains Context-to-Context because introducing inline
composition there would change its interaction and authority contract.

The command accepts `SOURCE [TARGET]`, `--from SOURCE --to TARGET`, and
`--memory TEXT --to TARGET`. An unambiguously non-Context Source becomes the
same single inline Memory, while a portable-looking missing name continues to
fail as a Context typo. The full classification and persistence rationale is
recorded in
[`context-or-inline-memory-operand-design-rationale.md`](context-or-inline-memory-operand-design-rationale.md).

The selected setup design does not move or relax Update's provider decoder,
complete-plan validation, final review, local/granted-target distinction,
compare-and-swap session replacement, application checkpoints, or Undo/Redo.
The later application-flow extraction changes only how the reviewed session
reaches the existing transaction selected by its mutation owner.

## Verification and remaining boundary

Adapter tests cover all four independent reach combinations, one focused
Memory per role, Source Memory plus recursive Target, distinct defaults,
full-UID forwarding, and a frozen local-plus-READ-granted catalog. Focused
semantic tests cover context-only neighbors, exact operation identity,
focused-Target ADD exclusion, schema round-trip, graph freshness, and the
descendant/focus incompatibility. The wider Update, authority, session,
endpoint, Study exact-prewarm, Apply, CAS, and Undo/Redo suite remains green.

Ordered 180×52 PTY evidence records the production command adapter from entry
through reviewed receipt and cancellation. The rebuilt component still does
not own new-Context naming or mode-dependent active roles; those capabilities
must be characterized before migrating Atomize or Meld.

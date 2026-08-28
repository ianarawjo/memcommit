# Console adapter ownership design rationale

Last reviewed: 2026-08-28.

## Decision

`memcommit.adapters.console` is the canonical owner of the `mem` executable,
its command adapters, and the operation-neutral terminal contracts shared by
line-oriented CLI and interactive TUI presentation. The former
`memcommit.adapters.interfaces.console` staging package moved here without a
compatibility facade.

The package keeps two explicit levels:

- `commands` owns Typer command registration and operation-specific console
  orchestration;
- top-level console modules and the nested `responses` and `selection`
  packages own reusable terminal routing, capability, text-safety, identity,
  progress, palette, response, and selection mechanics.

The package root re-exports only the lightweight route and terminal capability
contract. Importing `memcommit.adapters.console` must not assemble the Typer
entry point or command registry.

The generated-Memory completion preview is one concrete shared-console
component. Distill and Elaborate both publish operation-owned semantic results
as ordinary Memories, then pass the exact applied UID/content pairs to
`adapters.console.terminal.components.applied_memory_preview`. The component owns only
escaping, the twenty-row display bound, remainder disclosure, and Memory
foreground styling. It does not resolve endpoints, append Memories, create
checkpoints, or define either operation's receipt. Its former
`adapters.interfaces.cli.semantic_add` path is removed without a facade because
the component is neither an Add command nor an independent CLI interface.

## Motivation

The complete interfaces tree had been moved beneath `adapters` as a temporary
ownership staging boundary. Retaining a second `interfaces.console` owner after
the executable and command tree already lived at `adapters.console` made one
terminal surface appear to have two peers and left command, CLI, TUI, core
targeting, and report consumers importing a provisional namespace.

The moved modules are not a second console implementation. They are the common
contracts used by the existing implementation: plain-versus-TUI routing,
TTY detection, safe text projection, semantic colors, progress, compact
identity, structural Merge summaries, and shared Response and selection
interaction state. Consolidating them under one adapter owner makes that
dependency direction explicit without changing their behavior.

## Invariants

- Reusable console modules must not import `memcommit.adapters.console.commands`;
  command adapters may depend on reusable console modules, not the reverse.
- Text safety, semantic palette classification, response drafts, selection
  cursor state, and terminal capability remain process-local presentation
  contracts and acquire no application, provider, persistence, or mutation
  authority through this move.
- `responses` and `selection` retain their existing subpackage topology and
  typed values; no durable session schema, command grammar, focus behavior,
  marker, color, or rendered text changes.
- The old `memcommit.adapters.interfaces.console` path is retired rather than
  retained as a second compatibility owner.
- The now-empty `adapters.interfaces.cli` staging package is retired without a
  compatibility facade. Remaining `adapters.interfaces.tui` Viewer and
  Workbench packages stay staging surfaces pending their separate ownership
  review.

## Alternatives and remaining boundary

Keeping the shared modules under the staging package was rejected because it
preserved the duplicate console ownership that staging was intended to remove.
Moving them beneath `adapters.console.commands.shared` was rejected because
bootstrap, plain CLI, TUI, core targeting, and presentation consumers need the
contracts without depending on command registration or operation packages.
Splitting pure response and selection state into core was also rejected: their
invariants describe terminal cursor, focus, checked-value, and rendering
behavior rather than domain meaning.

Some TUI renderers still depend on the temporary `adapters.interfaces.tui`
surface, and the existing command-progress compatibility facade still forwards
to the canonical progress implementation. Those are later reviewed ownership
slices; neither justifies retaining the retired console staging package.

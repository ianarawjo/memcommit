# TUI Dialog Interface Ownership Rationale

## Problem

The Context-reach, flat-selection, and exact-name dialogs are reusable
terminal-interface components, but their implementations lived under
`memcommit.commands`. That location made operation-neutral interaction
mechanics appear to belong to the Import command and left the dependency
direction inconsistent with the rest of the shared TUI components.

## Decision

The existing implementation files move to
`memcommit.adapters.interfaces.tui.components`. Import's workbench uses those canonical
paths. Each former command module remains as a `sys.modules` alias to the
interface-owned module, rather than wrapping or copying its public function.

Context-reach and flat-selection move byte-for-byte. Exact-name changes only
the import of its already interface-owned exact-name control from the legacy
`commands.tui_primitives` compatibility path to its canonical component path;
normalizing that import reproduces the complete pre-move source bytes.

The alias preserves one module object regardless of import order. Consequently,
legacy-path monkeypatches and canonical-path imports observe the same globals,
while existing callers may continue importing the old path.

## Invariants and boundary

- Function signatures, defaults, validation, exceptions, key bindings,
  rendering, TTY checks, and input/output behavior remain unchanged.
- The implementation bytes match the pre-migration command-hosted files.
- The legacy facades define no functions or classes.
- The canonical module name and file location now reflect interface ownership;
  no broader dialog redesign or command behavior change is part of this move.
- No terminal snapshots are refreshed because the rendered interaction is
  unchanged.

Focused tests cover both legacy-first and canonical-first imports, module
identity, facade structure, the existing Import workbench behavior, and the
interface dependency direction. Exact-name additionally pins its normalized
pre-move source digest so the ownership move cannot conceal an implementation
rewrite.

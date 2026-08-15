# Meld shared TUI boundary

## Motivating problem

Meld still entered terminal presentation through two command-owned modules:
`commands.endpoint_setup_flows` assembled its A/B/C launch screen and
`commands.meld_shell` adapted a saved session into the shared Resolution
Workbench. This left an otherwise terminal-independent Meld application
boundary coupled to the historical command package.

The launch shape is wider than a fixed two-role picker. Symmetric Meld exposes
`A + B -> C`, disables direct-Memory focus, and allows C to be either an
eligible existing empty Context or a confirmed new exact Result Context name.
Directional Meld exposes only `A -> B`, gives A and B different authority
labels, and may focus one direct Memory when descendant reach is off.

## Shared component contract

`interfaces.tui.components.endpoint_setup` owns only the reusable interaction
mechanics:

- mode-dependent active role order and role labels;
- mode-dependent descendant and direct-Memory controls;
- explicit confirmation of an exact new Context name, rendered `NOT CREATED`;
- omission of hidden roles and hidden scope state from the returned typed
  draft; and
- dynamic focus traversal over only the controls visible in the selected mode.

The component does not discover Contexts, decide Meld authority, connect a
provider, create a session, or create the new Context. A new-name draft is
process-local and has `create=True`; the Meld application layer remains the
only code allowed to validate and materialize that reviewed result.

Mode changes clear a direct-Memory choice when the new mode does not expose
Memory focus. This prevents an invisible narrower scope from surviving in the
executable draft. Backspace remains ordinary text deletion while the exact-name
field owns focus.

## Operation adapter boundary

The intended dependency direction is:

```text
commands.meld (CLI orchestration)
  -> commands.meld_setup (freeze readable authority)
  -> interfaces.tui.operations.meld (setup and saved-session presentation)
  -> interfaces.tui.components (operation-neutral mechanics)
```

The CLI may open a TUI adapter, but the adapter does not invoke the CLI. Meld
runtime, provider, cache, receipt, and Apply semantics remain outside this
relocation. Historical command-owned modules remain import-only compatibility
facades where existing callers still need their names.

## Verification boundary

The migration requires three forms of evidence:

1. typed contract tests for mode/role capability projection and new-name
   invariants;
2. parity and operation tests proving the same Meld requests, reviews, and
   applications survive the import relocation; and
3. an ordered 180x52 color PTY capture covering setup entry, mode/endpoint
   transitions, result-name confirmation, review, exact application, receipt,
   and read-only result inspection.

The screenshots are behavior evidence, not a second implementation. They must
record exact keys, terminal size, profile/current Context, and durable mutation
at each step.

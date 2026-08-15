# Fit shared-assets follow-up

## Decision

Do not refactor Fit-specific presentation or interaction assets now. Fit must
join the repository-wide shared TUI/viewer consolidation later, rather than
creating a second common layer around Fit alone.

## Current boundary

- `memcommit.commands.fit` owns a bespoke plain-text `render_fit` projection;
  Fit does not currently have a standalone TUI.
- The interactive Fit action is embedded in the named Ground Cases flow.
  That shell already reuses the shared frame, scrollable-pane, multiline-input,
  theme, and keybinding components.
- Its Case cards, Fit status/detail projection, background-run messaging, and
  table composition still live in the Ground command adapter. The table also
  still depends on the legacy command-hosted `commands.tui_table` component.
- Fit's semantic report and immutable receipt remain application/domain data.
  They must not acquire prompt-toolkit, terminal styling, or clipboard state.

This is therefore partial reuse, not an absent common layer and not a complete
shared-assets migration.

## Deferred batch

Handle Fit together with the full semantic read-only result/viewer inventory:

1. freeze the common presentation invariants across Fit, Conformance, Audit,
   Distill, Summarize, Compare, and compatible Ground result projections;
2. keep each operation's typed document, row meaning, status vocabulary,
   receipt freshness, and available actions operation-owned;
3. consolidate compatible frame, scrolling, table, focus, clipboard (`y`/`Y`),
   progress, and read-only back-navigation mechanics under the interface TUI
   owners;
4. make both plain CLI and TUI projections consume the same operation result
   without importing one another;
5. migrate the compatible operations as one characterized family, with
   cross-operation parity tests and refreshed ordered PTY captures;
6. remove the legacy component only after every known consumer has moved.

## Intentional non-goal now

Do not move `render_fit`, split the Ground shell, introduce a Fit-only viewer,
or change Fit behavior, output, keybindings, receipts, or screenshots as part
of the current Ground/Fit work. This note records the debt so it can be handled
once, consistently, during the planned `TUI-05` shared-viewer migration.

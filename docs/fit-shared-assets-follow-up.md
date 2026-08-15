# Fit shared-assets follow-up

## Decision

The earlier deferral condition was met on 2026-08-15: the repository-wide
operation and shared-TUI ledgers now exist, and Fit is the first additional
semantic read/report operation migrated through them. The migration must reuse
the existing semantic Viewer, clipboard, console-routing, and background-turn
owners. It must not create a second Fit-only common layer.

## Current boundary

- The CLI command remains composition only. Its stable plain projection lives
  under `interfaces.cli`, while the standalone interactive projection lives
  under `interfaces.tui.operations.fit`.
- The interactive Fit action is embedded in the named Ground Cases flow.
  That shell already reuses the shared frame, scrollable-pane, multiline-input,
  theme, and keybinding components.
- Its Case cards, Fit status/detail projection, and table composition still
  live in the Ground command adapter. The table also still depends on the
  legacy command-hosted `commands.tui_table` component. Only the blocking Fit
  turn lifecycle moves to the shared background-turn component in this slice.
- Fit's semantic report and immutable receipt remain application/domain data.
  They must not acquire prompt-toolkit, terminal styling, or clipboard state.

This is therefore partial reuse, not an absent common layer and not a complete
shared-assets migration.

## Current migration slice

Handle Fit as one bounded vertical slice of the semantic result inventory:

1. keep Fit's typed report, judgment vocabulary, receipt identity, Ground
   revision freshness, and provider execution operation-owned;
2. make independent plain CLI and TUI projections consume that typed report;
3. reuse the shared semantic Viewer for section navigation and read-only close,
   and the shared clipboard component for focused `y` and whole-document `Y`;
4. reuse `BackgroundExecutorTurn` for the embedded Ground Fit action so its
   provider call does not freeze prompt-toolkit or disappear during close;
5. protect non-TTY plain output, current/stale receipt reopening, clipboard
   scope, duplicate-run exclusion, and close-after-turn with tests;
6. refresh ordered 180x52 PTY evidence for the changed interactive paths.

## Remaining boundary

Do not move the Ground Case cards or legacy table merely to make this Fit slice
look complete. `commands.tui_table` still has multiple Ground consumers and
requires a separately characterized migration. Conformance, Audit, Distill,
Compare, and other compatible reports remain later `TUI-05` candidates; Fit's
adapter is evidence for the shared mechanics, not a template that determines
their semantic documents.

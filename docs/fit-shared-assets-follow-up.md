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
- Its saved-Memory list, compact Fit-mark projection, and Enter detail still
  live in the Ground command adapter. The former named-Ground `V` table was
  later removed as a duplicate of that list/detail path; the blank first-turn
  preview remains the separate Ground consumer of the command-hosted
  `commands.tui_table` component. Only the blocking Fit turn lifecycle moved to
  the shared background-turn component in this slice.
- Fit's semantic report and immutable receipt remain application/domain data.
  They must not acquire prompt-toolkit, terminal styling, or clipboard state.

This is therefore partial reuse, not an absent common layer and not a complete
shared-assets migration.

## Current migration slice

Handle Fit as one bounded vertical slice of the semantic result inventory:

1. keep Fit's typed report, judgment vocabulary, receipt identity, Ground
   revision freshness, and provider execution operation-owned;
2. make a one-line plain CLI projection and compact TUI projection consume
   that typed report without discarding receipt evidence;
3. reuse the shared semantic Viewer for section navigation and read-only close,
   and the shared clipboard component for focused `y` and whole-document `Y`;
4. reuse `BackgroundExecutorTurn` for the embedded Ground Fit action so its
   provider call does not freeze prompt-toolkit or disappear during close;
5. protect one-line non-TTY output, the `·`/`✓`/`!`/`◷` contract,
   receipt reopening, clipboard scope, duplicate-run exclusion, and
   close-after-turn with tests;
6. refresh ordered 180x52 PTY evidence for the changed interactive paths.

## Remaining boundary

Do not move the Ground Memory list/detail or blank-Ground preview table merely
to make this Fit slice look complete. The named-Ground table was removed only
after USE, FIT, and Enter detail gave each remaining surface one distinct job;
that is not a general table-component migration. Conformance, Audit, Distill,
Compare, and other compatible reports remain later `TUI-05` candidates; Fit's
adapter is evidence for the shared mechanics, not a template that determines
their semantic documents.

## Verification

The selected slice is implemented and verified by focused Fit, semantic
Viewer, Summarize parity, and named-Ground tests. The ordered true-color PTY
record is under `docs/screenshots/mem-fit-shared-viewer-20260815` and covers
provider progress, current, issue, and stale standalone results, focused `y`,
complete `Y`, Ground's empty/current marks, duplicate-run exclusion, deferred
close, one receipt, and unchanged Ground content.

The repository-wide matrix remains `MIGRATING`, because this proves one Fit
vertical slice rather than completing Conformance, Audit, Distill, Compare, or
the remaining command-hosted viewers. The blank-Ground draft table remains a
named follow-up rather than hidden unfinished work in this slice.

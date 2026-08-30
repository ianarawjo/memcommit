# Fit shared-assets follow-up

## Revised decision

The 2026-08-15 migration proved that Fit could use the shared semantic Viewer,
clipboard, console router, and background-turn components. Later use showed
that the standalone Viewer exposed more interaction than the operation needs.
Fit detects compatibility; it has no selection, revision, or Apply action to
review. As of 2026-08-21, standalone Fit therefore returns one compact receipt
in every terminal and no longer consumes the Viewer, clipboard, or console
router.

This is a deliberate product boundary, not a rejection of the shared
components. Operations with navigable evidence or user decisions continue to
use them. General Fit is one grouped target line for every verdict:
`FIT · VERDICT · [TARGETS: TYPE value, value, TYPE value ...]`. Contexts,
direct Memories, and literal aliases share that one bracket without expanding
their bodies or provenance relationships. Ground Fit first states the complete
result as `FIT · VERDICT · [TARGETS: GROUND name] · fraction`; each non-successful
Rule–Example check is one uninterrupted line containing its local
classification, both role/Memory labels, both exact bodies, and `↔`. Stored
reasons are not expanded and fitting detail remains omitted.

The compact CLI consumes typed receipt segments and resolves only its
`YES/MAY/NO` token through the shared terminal judgment palette. It does not
reuse EDIT/EMBED/REMOVE action meaning or tint the complete relationship line.
Pipes and `NO_COLOR` preserve the exact ANSI-free text.

## Current boundary

- The command owns composition and its terminal-safe receipt projection under
  `adapters.console.commands.fit`; the retired `interfaces.cli` staging package
  retains no presentation facade.
- General Fit remains process-local and creates no durable receipt. Stored
  input origins remain typed application data for authority and exact
  revalidation, not a reason to expose the whole frozen frame in a Viewer.
- Ground Fit keeps its immutable receipt, revision freshness, and complete
  internal evidence. The small terminal projection does not discard those
  fields.
- Physical Ground Fit is explicit and line-oriented. The removed JSON Ground
  shell's AUTO-FIT and saved-Memory projection are historical only.

## Compatibility and evidence

The retired `--plain` and `--tui` flags are absent, so argument parsing rejects
them before storage or provider construction. ANSI-free output follows
terminal capability, pipes, and `NO_COLOR`. Historical Viewer screenshots under
`agent-records/docs/screenshots/mem-fit-shared-viewer-20260815`,
`agent-records/docs/screenshots/mem-general-fit-20260815`, and the Viewer states in
`agent-records/docs/screenshots/ground-unified-fit-20260816` document the superseded route;
they are not current interface specifications.

Focused tests cover grouped two- and three-target general lines for every verdict,
the operation-wide Ground header, two-sided local Ground issues, retained typed
split readings for `MAY`, repeated stored operands, stale suppression, the
compatibility flag, absence of the Viewer route, immutable receipt reopening,
and physical Ground receipt freshness. The former named-Ground background-turn
tests were deleted with that shell.

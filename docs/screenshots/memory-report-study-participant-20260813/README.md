# Trace/Rationale on the task-1 participant study profile

This ordered capture uses the current real study Context
`task-1/participant`, rather than the small deterministic fixture used by the
shared-launcher regression set. The selected row is the first real Memory in
`task-1/participant/construction-updates/building-access` and begins with
`Modify campus-wiki/building-access`.

The real data also exposes an important interpretation boundary. The selected
row says `0 recorded changes`, while its Trace result separately classifies the
current state as `HISTORY_GAP · UNRECORDED`: the Context differs from
reconstructable checkpoint history, but that gap is not counted as evidence of
one recorded modification.

## Reproduction frame

- Command: `python docs/screenshots/memory-report-study-participant-20260813/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Current Context: `task-1/participant`
- PTY: `180` columns × `52` rows; `TERM=xterm-256color`,
  `COLORTERM=truecolor`, and `NO_COLOR` unset
- Provider boundary: Rationale uses `recorded-only`; neither path connects a
  provider
- Persistence boundary: command-attempt logging is disabled, and the script
  hashes every Context file plus `state.json` before and after each flow. The
  capture fails if any durable study data changes.
- Entry-point note: the child invokes the Trace/Rationale command functions
  directly because an unrelated in-progress Summarize interface move currently
  leaves the repository-wide CLI import incomplete. The command functions and
  terminal UI exercised here are the same ones routed by `mem trace` and
  `mem rationale` once that import boundary is intact.

## Ordered interaction

| Image | Input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-trace-exact-entry.png` | Open Trace | `RANGE` starts at `THIS CONTEXT ONLY`; participant root is empty | None |
| `02-trace-descendants.png` | `Right` | Real construction-update Contexts and Memories become visible | None |
| `03-trace-study-memory-focused.png` | `Tab`, `Down` × 3 | Blue `CONTEXTS & MEMORIES` frame contains the real building-access Memory and `0 recorded changes` | None |
| `04-trace-result.png` | `Enter` | Shared temporal Trace result opens for the exact Memory | None |
| `05-trace-verification.png` | `q` | Store digest remains unchanged | None |
| `06-rationale-exact-entry.png` | Open recorded-only Rationale | Same exact-range launcher | None |
| `07-rationale-descendants.png` | `Right` | Same real descendant data | None |
| `08-rationale-study-memory-focused.png` | `Tab`, `Down` × 3 | Same target frame and retained-change count | None |
| `09-rationale-result.png` | `Enter` | Recorded-only Rationale report opens | None |
| `10-rationale-verification.png` | `q` | Store digest remains unchanged | None |

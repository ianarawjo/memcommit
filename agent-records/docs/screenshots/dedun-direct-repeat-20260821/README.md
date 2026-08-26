# Repeated Dedun direct-execution capture

This ordered set records the changed flagless `mem dedun` entry contract. An
ordinary invocation analyzes and applies the exact current Context directly;
it does not open target setup, a report Viewer, survivor choices, or the
content-free Recents launcher. The second invocation is the regression case:
a completed Dedun recent exists, but execution still proceeds directly.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/dedun-direct-repeat-20260821/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated temporary default Profile;
  `quality/direct-dedun` is current
- Source: two directly owned, differently worded but semantically equivalent
  Memories
- Semantic boundary: a deterministic host fixture supplies the same typed
  `SEMANTIC_EQUIVALENT` report on the first run and an empty report after Apply;
  the production CLI, plan, atomic Apply, attempt ledger, and receipt paths run
  unchanged
- PTY: live and verified `180` columns × `52` rows
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR`
  unset; command-attempt logging remains enabled so the second run has a real
  completed Recent to bypass
- Rendering: cumulative real ANSI PTY streams replayed at full canvas; each PNG
  retains matching `.typescript` and `.txt` evidence

## Ordered interaction log

| Capture | Exact command | Input since preceding capture | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-first-direct-apply` | `mem dedun` | launch | Compact success receipt names absorbed/survivor counts, checkpoint, Review route, and Undo recovery; no full-screen surface opens | One redundant Memory removed in one Dedun checkpoint |
| `02-second-direct-noop` | `mem dedun` | `Enter` at the capture-only continuation gate | Direct no-applicable result appears even though the first completed attempt is now a Dedun Recent; `RECENTS OR SELECT` and `SELECT A TARGET` are absent | None |
| `03-read-only-verification` | same process | `Enter` at the second capture-only continuation gate | Store reload confirms one Memory, one checkpoint, one content-free Dedun Recent, two analyses, and unchanged current Context | None |

The fixture keeps semantic-provider latency out of the visual regression while
retaining Dedun's real application and history boundaries. The read-only
`mem find-redundancies --select` operation remains the explicit route for
multi-target/Recents navigation and evidence inspection before mutation.

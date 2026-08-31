# `mem help` History section capture log

This ordered capture verifies the catalog- and application-owned subdivision
of the existing `HISTORY & RECOVERY` Help family. The family description and
all eight operation records remain unchanged; BY KIND adds only neutral,
non-focusable `INSPECTION` and `RECOVERY` divider rows. A–Z remains flat.

## Reproduction frame

- Capture command: `python agent-records/docs/screenshots/mem-help-history-sections-20260830/capture.py`
- Command under observation: `mem help`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile / current Context: not consulted / not consulted
- PTY: `180` columns × `52` rows; the raw stream includes the verified `stty size`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: the real cumulative ANSI PTY stream is replayed through `pyte`
  and drawn at the complete terminal-canvas size. Raw `.typescript` and plain
  `.txt` evidence remain beside every PNG.
- Color verification: the capture rejects a stream without foreground and
  background ANSI styles. It also verifies that the selected command alone
  receives the blue focus background while both section labels remain neutral.

## Ordered interaction log

| Image | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-by-kind-entry.png` | Run `mem help` | Initial BY KIND Help entry at `BROWSE & NAVIGATE` | None |
| `02-history-inspection-focused.png` | `Tab` ×7 | The focused `HISTORY & RECOVERY` box retains its description and shows `mem log` under the first `INSPECTION` rule | None |
| `03-history-recovery-focused.png` | `Down` ×4 | The same box shows both internal rules while continuous command traversal crosses the non-focusable divider and focuses `mem checkpoint` under `RECOVERY` | None |
| `04-trace-expanded.png` | `Up` ×2, then `Right` | `mem trace` retains its existing expanded Flow, Execution, Effect, Range, and Forms inside the sectioned family | None |

After the final capture, `Q` closes the read-only full-screen Help browser with
exit status 0. No state is published by any step.

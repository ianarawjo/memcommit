# Rebuilt Status Help verification

This focused ordered capture set verifies the Help contract for the rebuilt
`mem status` operation. Every image comes from the actual installed `mem`
executable in a color-capable PTY with `NO_COLOR` removed,
`TERM=xterm-256color`, and `COLORTERM=truecolor`. Help does not consult a
Profile or current Context, and every state is read-only.

| Capture | Exact command | PTY | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- | --- |
| `01-wide-collapsed` | `mem help` | `180×52` | none | complete Status Summary and `USE WHEN` columns | none |
| `02-wide-expanded` | same process | `180×52` | `Right` | Status Flow, Execution, Effect, Range, and all four forms | none |
| `03-compact-collapsed` | separate `mem help` | `100×30` | `Down` | complete wrapped Summary and `USE WHEN` | none |
| `04-compact-expanded` | same compact process | `100×30` | `Up`, `Right` | wrapped Flow, Execution, Effect, Range, and first form | none |
| `05-compact-forms` | same compact process | `100×30` | `Down` ×3 | remaining forms including recursive scope | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log.

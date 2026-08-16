# `mem help` Merge wording verification

This ordered capture set verifies that deterministic Merge is described as
Source-only addition plus explicit Source/Target selection, while `USE WHEN`
stays focused on the copied-or-branched Context scenario instead of requiring
the user to understand stored-identity mechanics first.

Every image comes from the actual installed `mem` executable in a
color-capable PTY with `NO_COLOR` removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. The wide pair uses `180×52`; the compact pair uses
`100×30`. The raw stream is checked for foreground and background ANSI styles
and rendered directly. Help does not consult a Profile or current Context, and
every state is read-only.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-wide-collapsed` | `mem help` | `180×52` | not consulted / not consulted | `Shift-Tab`, `Right` to A–Z, `Tab`, `Home`, `Down` ×36 | collapsed Merge Summary and scenario-based `USE WHEN`; Profile owns focus so the complete Merge row remains visible | none |
| `02-wide-expanded` | same process | `180×52` | not consulted / not consulted | `Up`, `Right` | expanded deterministic Merge contract and first form | none |
| `03-compact-collapsed` | separate `mem help` | `100×30` | not consulted / not consulted | `Shift-Tab`, `Right` to A–Z, `Tab`, `Home`, `Down` ×36 | stacked compact Summary and `USE WHEN`; Profile owns focus so the complete Merge row remains visible | none |
| `04-compact-expanded` | same compact process | `100×30` | not consulted / not consulted | `Up`, `Right` | compact expanded Merge contract and first form | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log.

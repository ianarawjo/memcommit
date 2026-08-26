# `mem add` copy-or-link Help verification

This ordered capture set verifies the expanded Add `copy-or-link` detail. It
distinguishes literal new content, independent branch/copy work, immutable
Memory or Context Reference snapshots, and live Memory or Context Embeds. The
collapsed row stays compact; expansion adds the `COPY OR LINK` explanation
before the exact CLI forms and renders every alternative with a literal `-`
marker.

Every image comes from the actual installed `mem` executable in a
color-capable PTY with `NO_COLOR` removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. The wide sequence uses `180×52`; the compact sequence
uses `100×30`. Help does not consult a Profile or current Context, and every
state is read-only.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-wide-collapsed` | `mem help` | `180×52` | not consulted / not consulted | `Shift-Tab`, `Right`, `Tab`, `Home` | A-Z Add row before expansion | none |
| `02-wide-expanded` | same process | `180×52` | not consulted / not consulted | `Right` | Add meaning, structured copy-or-link comparison, and CLI forms | none |
| `01-compact-collapsed` | separate `mem help` | `100×30` | not consulted / not consulted | `Shift-Tab`, `Right`, `Tab`, `Home` | compact A-Z viewport before expanding its first-row Add cursor | none |
| `02-compact-expanded` | same compact process | `100×30` | not consulted / not consulted | `Right` | wrapped Add comparison with named alternatives | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log. The interactive process closes
with `q` and exits with status 0.

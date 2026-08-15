# `mem help` Meld wording verification

This ordered capture set verifies the reviewed Meld explanation, the separate
symmetric and directional flows, and one concrete command example for each
mode. Every image comes from the actual installed `mem` executable in a
color-capable `180×52` PTY with `NO_COLOR` removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. The raw stream is checked for foreground and background
ANSI styles and rendered directly; no synthetic Help fixture is used.

Help does not consult a Profile or current Context. Every captured state is
read-only and the process exits with `q`.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-collapsed-meld` | `mem help` | `180×52` | not consulted / not consulted | `Tab` ×3, `Down` ×6 | collapsed Meld row with reviewed explanation and use case | none |
| `02-expanded-contract` | same process | `180×52` | not consulted / not consulted | `Right` | expanded Flow, Effect, Range, and first generic form | none |
| `03-symmetric-example` | same process | `180×52` | not consulted / not consulted | `Down` ×4 | concrete symmetric Result example focused as Form 5 | none |
| `04-directional-example` | same process | `180×52` | not consulted / not consulted | `Down` ×4 | concrete directional Baseline example focused as Form 9 | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log.

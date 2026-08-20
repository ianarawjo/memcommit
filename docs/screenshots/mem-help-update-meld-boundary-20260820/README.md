# Update-versus-Meld Help boundary

This ordered capture set verifies that Update and Meld retain their existing
collapsed Help copy while both expanded records expose the same concise
`UPDATE VS. MELD` semantic boundary. Update is described as revision-oriented;
Meld is described as merge-oriented. The note does not claim that edit
capability separates the operations.

All images use the full `180×52` viewport. The interactive states come from the
actual installed `mem help` TUI in a color-capable PTY with `NO_COLOR` removed,
`TERM=xterm-256color`, and `COLORTERM=truecolor`. The raw stream is checked for
foreground and background ANSI styles and rendered directly. Help does not
consult a Profile or current Context, and every state is read-only.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-update-meld-collapsed` | `mem help` | `180×52` | not consulted / not consulted | `Tab` ×4, `Down` ×6 | Update focused; no expanded boundary note | none |
| `02-update-note-expanded` | same process | `180×52` | not consulted / not consulted | `Right` | Update expanded with the shared revision-oriented versus merge-oriented note | none |
| `03-meld-note-expanded` | same process | `180×52` | not consulted / not consulted | `Left`, `Down`, `Right` | Meld expanded with the byte-identical shared note | none |
| `04-read-only-public-verification` | `python -c` public Help detail lookup | `180×52` | not consulted / not consulted | separate process | Both operation-local detail IDs resolve to `SEMANTIC_BOUNDARY` and the same body | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log.

# Role-aware Dedup / Dedun Help

This ordered capture set records the public Help contract introduced by the
role-aware exact layer:

- `mem dedup` applies provider-free exact cleanup only within the same direct
  item role;
- Memory, Embed, and Reference roles never merge with one another; and
- `mem dedun` is the wider operation, combining that exact layer with semantic
  redundancy only among directly owned Memories.

Every image comes from the actual `mem help` command in a color-capable
`180×52` PTY with `NO_COLOR` removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. The raw stream is checked for foreground and background
ANSI styles. Help consults no Profile or current Context, and every state is
read-only.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-adjacent-operations` | `mem help` | `180×52` | not consulted / not consulted | `Shift-Tab`, `Right` to A–Z, `Tab`, `Home`, `Down` ×12 | adjacent Dedun and Dedup summaries with the wider-DUN and same-role-exact distinction | none |
| `02-dedun-expanded` | same process | `180×52` | not consulted / not consulted | `Right` | role-aware DUP plus direct-Memory semantic DUN flow, partial-overlap boundary, and command form | none |
| `03-dedup-expanded` | same process | `180×52` | not consulted / not consulted | `Left`, `Down`, `Right` | deterministic role-aware exact grouping, cross-role exclusion, checkpoint effect, and no-provider boundary | none |

Each numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log. Regenerate with:

```sh
python agent-records/screenshots/dedup-role-aware-help-20260823/capture.py
```

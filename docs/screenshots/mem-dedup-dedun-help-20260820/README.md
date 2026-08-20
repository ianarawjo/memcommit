# Dedup / Dedun Help distinction

This ordered capture set verifies the public vocabulary boundary:

- `dup` means byte-identical stored content, so `mem dedup` is deterministic
  and applies immediately;
- `dun` means semantic redundancy, so `mem dedun` owns semantic discovery,
  review, and exact Apply; and
- the former `find-redundancies` and `consolidate` stages are not separate Help
  operations or ordinary invocation forms.

Every image comes from the actual installed `mem help` command in a
color-capable `180×52` PTY with `NO_COLOR` removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. The raw stream is checked for foreground and background
ANSI styles. Help consults no Profile or current Context and all states are
read-only.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-adjacent-operations` | `mem help` | `180×52` | not consulted / not consulted | `Shift-Tab`, `Right` to A–Z, `Tab`, `Home`, `Down` ×12 | adjacent Dedun semantic summary and Dedup exact summary; old split operations absent | none |
| `02-dedun-expanded` | same process | `180×52` | not consulted / not consulted | `Right` | semantic execution, redundancy-group flow, the `PARTIAL OVERLAP` whole-Memory boundary with Atomize-first guidance, review-before-Apply effect, and only the simple `mem dedun` forms | none |
| `03-dedup-expanded` | same process | `180×52` | not consulted / not consulted | `Left`, `Down`, `Right` | deterministic exact-content grouping, immediate checkpoint effect, and no provider/TUI boundary | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log. Regenerate with:

```sh
python docs/screenshots/mem-dedup-dedun-help-20260820/capture.py
```

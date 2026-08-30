# Historical Dedup / Dedun Help distinction

This ordered capture set verifies the public vocabulary boundary:

- `dup` means byte-identical stored content, so `mem dedup` is deterministic
  and applies immediately;
- `find-redundancies` owns read-only semantic analysis and review, with the old
  `find-duplicates` spelling folded into its Help row; and
- at capture time, `dun` meant semantic redundancy Apply and `mem dedun`
  entered survivor review before exact Apply. That workbench and its hidden
  `consolidate` replay route were retired on 2026-08-30; current Dedun applies
  its deterministic survivor immediately and retains the evidence for Review.

Every image comes from the actual installed `mem help` command in a
color-capable `180×52` PTY with `NO_COLOR` removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. The raw stream is checked for foreground and background
ANSI styles. Help consults no Profile or current Context and all states are
read-only.

## Ordered interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-adjacent-operations` | `mem help` | `180×52` | not consulted / not consulted | `Shift-Tab`, `Right` to A–Z, `Tab`, `Home`, `Down` ×12 | adjacent applying Dedun summary and deterministic Dedup summary | none |
| `02-dedun-expanded` | same process | `180×52` | not consulted / not consulted | `Right` | semantic execution, redundancy-group flow, the `PARTIAL OVERLAP` whole-Memory boundary with Atomize-first guidance, review-before-Apply effect, and only the simple `mem dedun` forms | none |
| `03-dedup-expanded` | same process | `180×52` | not consulted / not consulted | `Left`, `Down`, `Right` | deterministic exact-content grouping, immediate checkpoint effect, and no provider/TUI boundary | none |
| `04-find-redundancies` | same process | `180×52` | not consulted / not consulted | `Left`, `Home`, `Down` ×24 | canonical read-only finder row with `find-duplicates` folded as a hidden exact alias | none |
| `05-find-redundancies-expanded` | same process | `180×52` | not consulted / not consulted | `Right` | read-only effect, frozen readable-frame range, and canonical command forms | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log. Regenerate with:

```sh
python agent-records/docs/screenshots/mem-dedup-dedun-help-20260820/capture.py
```

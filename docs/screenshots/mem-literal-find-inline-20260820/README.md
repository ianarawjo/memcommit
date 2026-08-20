# `mem find PATTERN` inline terminal verification

This ordered set records the actual `mem` executable in a color-capable
`180×52` PTY. `NO_COLOR` is removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. The active Profile is
`study-20260819T175451Z-5ce5d722`, and the current Context is
`practice/source`.

The inline renderer is intentionally ANSI-independent: the complete result
remains understandable as text, and the raw stream must not enter the
alternate-screen buffer. Find remains read-only.

## Interaction log

| Capture | Exact command | PTY | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- | --- |
| `01-before-read-only-status` | `mem status -s` | `180×52` | command launch | `practice/source` has 17 Memories and 5 checkpoints before Find | none |
| `02-inline-pattern-result` | `mem find "xxxxxx"` | `180×52` | command launch | a complete no-match result prints inline without full-screen pattern controls or alternate-screen entry | none |
| `03-after-read-only-status` | `mem status -s` | `180×52` | Find exited | the exact pre-Find status is unchanged | none |

Each state has the raw `.typescript`, terminal-text `.txt`, and full-canvas
`.png` artifact beside this log. `capture.py` asserts the exact terminal size,
unchanged before/after status, successful Find exit, and absence of alternate
screen control sequences.

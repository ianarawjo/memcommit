# `mem help` current BY KIND entry capture

This capture records the current interactive `mem help` entry screen rather
than the alphabetical inventory printed outside a TTY.

## Reproduction frame

- Capture command: `python agent-records/screenshots/mem-help-current-entry-20260824/capture.py`
- Command under observation: `mem help`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile: `study-20260824T114456Z-3e75ccdf`
- Current Context: `practice/rule`
- PTY: `180` columns × `52` rows; the raw stream includes the verified `stty size`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: the real cumulative ANSI PTY stream is replayed through `pyte`
  and drawn at full terminal-canvas size. The raw `.typescript` and plain
  `.txt` forms remain beside the PNG.
- Color verification: the capture requires foreground and background ANSI
  styles before succeeding.

## Ordered interaction log

| Image | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-by-kind-entry.png` | Run `mem help` | Initial `BY KIND` Help view, beginning with Core Concepts and `BROWSE & NAVIGATE` | None |

After the capture, `Q` closes the read-only full-screen Help browser with exit
status 0. The alternate screen erases itself on exit, so the requested initial
screen is the complete visible evidence set for this one-state capture.

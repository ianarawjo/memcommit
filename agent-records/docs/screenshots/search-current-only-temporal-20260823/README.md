# Search current-only time wording

This ordered set records the materially changed `mem search` interaction:
time-oriented wording remains part of the current-memory query and no longer
selects retained History Search. The workbench is the real prompt-toolkit UI in
a color-capable `180 × 52` PTY. A typed local response replaces network access
so the current-only mode and interaction states are deterministic. `NO_COLOR`
is removed, `TERM=xterm-256color`, `COLORTERM=truecolor`, and 24-bit
prompt-toolkit color are set.

| Image | Command / preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-search-entry.png` | `mem search` workbench entry | `practice/source` exact current scope; empty query | none |
| `02-time-wording-entered.png` | type `a is apple during recess` | time word remains ordinary query text; no History mode | none |
| `03-current-search-running.png` | Enter | ordinary `SEARCHING` state | none |
| `04-current-memory-result.png` | typed current provider response | one current `practice/source` Memory; no History result type | none |
| `05-current-result-checked.png` | Space | current result checked; Save As remains staged only | none |
| `06-read-only-verification.png` | Ctrl-C | current-only/read-only close receipt; no result save or Source mutation | none |

`capture.py` verifies the PTY dimensions in the child, preserves every raw ANSI
stream beside the PNG/text projection, and requires both foreground and
background color sequences.

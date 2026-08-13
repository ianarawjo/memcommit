# `mem help` BY KIND Tab path and A–Z boundary verification

These captures reproduce `mem help` with the real executable in color-capable
`180×52` and `180×86` PTYs. They first verify that Tab follows every visible
`BY KIND` category box in screen order before reaching `INVENTORY VIEW`, then
verify the A–Z projection boundary. The capture removes `NO_COLOR`, sets
`TERM=xterm-256color` and `COLORTERM=truecolor`, verifies both live sizes with
`stty size`, and checks that the raw PTY streams contain ANSI styles. The taller
viewport is intentional: it exposes the spare space below the complete A–Z
inventory that does not exist at the default height.

The command runs with a generated temporary `HOME`. Help is read-only, so no
Profile or current Context is created, loaded, or mutated. The capture script
also asserts that both the A–Z box and the pinned bottom rule end in column 179,
while column 180 remains the scrollbar gutter. In the tall capture it further
asserts that every spare row after `update` remains inside the box and that the
closing border is directly above the pinned rule.

## Ordered interaction log

| Capture | Exact command | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|
| `01-by-kind-entry` | `mem help` | none / none | none | initial `BY KIND` inventory with `CONTEXTS` focused | none |
| `02-memories-focused` | same | none / none | `Tab` | `MEMORIES` is the next focused kind | none |
| `03-search-explain-focused` | same | none / none | `Tab` | `SEARCH & EXPLAIN` is focused | none |
| `04-analyze-transform-focused` | same | none / none | `Tab` | `ANALYZE & TRANSFORM` is focused | none |
| `05-history-recovery-focused` | same | none / none | `Tab` | `HISTORY & RECOVERY` is focused | none |
| `06-ground-evaluation-focused` | same | none / none | `Tab` | `GROUND & EVALUATION` is focused | none |
| `07-profile-sharing-focused` | same | none / none | `Tab` | `PROFILE & SHARING` is focused | none |
| `08-system-focused` | same | none / none | `Tab` | `SYSTEM` is focused | none |
| `09-view-focused` | same | none / none | `Tab` | after the final kind, `INVENTORY VIEW` owns focus | none |
| `10-a-z-selected` | same | none / none | `Right` | `A–Z` is selected while VIEW retains focus | none |
| `11-a-z-list-boundary` | same | none / none | `Tab` | A–Z list focused; box and bottom rule share the same right edge | none |
| `12-a-z-tall-viewport-fill-180x86` | `mem help` in `180×86` | none / none | `Tab` ×8, `Right`, `Tab` | spare rows below `update` remain inside the A–Z box | none |

After the final capture, `Q` cancels the read-only browser with exit status 0.
The full-screen application erases itself on exit, so there is no separate
visible cancellation receipt to capture.

The capture script is [`capture_help_a_z.py`](./capture_help_a_z.py). Every
numbered state has a raw `.typescript`, terminal-text `.txt`, and full-canvas
`.png` artifact.

# Terminal status copy captures

These captures verify representative changed surfaces in a color-capable
`180×52` PTY. They exercise the actual prompt-toolkit screens and preserve the
raw ANSI stream beside the rendered PNG and text projection.

1. `01-ground-draft` — `$ mem ground`; current Context
   `capture/reference`; initial blank draft; no provider call; captured at
   entry, then `Escape`; no durable mutation.
2. `02-compare-task-setup` — `$ mem compare` endpoint setup; current Context
   `capture/reference`; captured at entry, then `Escape`; the child verifies
   both Context files remain byte-identical.
3. `03-summarize-result` — `$ mem summarize capture/reference`; direct scope,
   two frozen source Memories; captured in the immutable result viewer, then
   `Escape`; no durable mutation.

Reproduce with:

```console
python agent-records/screenshots/terminal-status-copy-20260822/capture.py
```

The capture process removes `NO_COLOR`, sets `TERM=xterm-256color`, enables
true color, requests a `180×52` PTY, and fails if ANSI or true-color styles are
missing.

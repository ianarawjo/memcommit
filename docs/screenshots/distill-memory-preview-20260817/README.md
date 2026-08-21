# Distill direct-item preview evidence

These captures exercise the actual `mem distill capture/cases --tui` command
and shared Context preview controller in a color-capable `180×52` PTY. The
capture removes `NO_COLOR`, sets `TERM=xterm-256color` and
`COLORTERM=truecolor`, and verifies foreground and background ANSI styles in
the retained raw stream. A disposable Store contains two Contexts; provider
construction is replaced with an assertion because previewing must remain a
local read-only action.

| Capture | Exact command / preceding key | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-distill-entry` | `mem distill capture/cases --tui` | selected `capture/cases`; no direct-item rows loaded | none |
| `02-lowercase-m-this-context` | `m` | only `capture/cases` items visible; footer says `m THIS Context: hide items` and still offers `M EVERY Context: show items` | none |
| `03-uppercase-m-every-context` | `M`, then `Down` ×4 through the read-only viewport stops | `capture/other` item is loaded and focused; footer says the global action will hide every Context | none |
| `04-read-only-verification` | `q`, then `mem show --context capture/cases` and `mem show --context capture/other` | provider calls remain zero and both Context records are byte-identical | none |

Each state has a raw `.typescript`, extracted `.txt`, and native-size `.png`.
Reproduce from the repository root with:

```bash
.venv/bin/python docs/screenshots/distill-memory-preview-20260817/capture.py
```

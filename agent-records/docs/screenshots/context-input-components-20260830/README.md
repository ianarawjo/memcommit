# Context input component comparison

These captures compare the current terminal shape of four Context-oriented
controls without changing their implementations. Every command ran in a real
`180x52` color PTY against an isolated Store with current Context
`work/current`; each screen was cancelled before durable work and made no
provider call.

| Image | Exact command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-context-selector.png` | `mem add` | none | Add's single Context target tree | none; Escape cancelled |
| `02-direct-memory-selector.png` | `mem edit` | none | Context tree with the selected Context's direct Memory rows | none; Escape cancelled |
| `03-context-name-editor.png` | `mem init` | none | exact new-name field with a local parent tree | none; Escape cancelled |
| `04-readable-scope-editor.png` | `mem query` | none | direct readable-scope input and transient Browse affordance | none; Ctrl-C cancelled |

Capture environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
`PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, `NO_COLOR` unset. The PNGs are
rendered from the actual ANSI PTY streams by `capture.py`; matching plain-text
and `.typescript` evidence is retained beside each image.

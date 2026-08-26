# Summarize Context-first and clipboard workbench capture log

This ordered set records the Context-first Summarize topology, the empty
Summary execution action, all three range choices, and scoped plain-text copy.
It supersedes the Run-first evidence under
`mem-summarize-both-workbench-20260813/`.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/mem-summarize-context-first-workbench-20260813/capture.py`
- TUI command: `mem summarize task-1/participant --tui`
- Plain compatibility command: `mem summarize task-1/participant --plain`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Initial TUI range: `BOTH`; explicit `-d` and `-r` retain their individual
  initial selections
- PTY: `180` columns × `52` rows, `TERM=xterm-256color`, true color,
  `NO_COLOR` unset
- Clipboard boundary: the command's ordinary plain-text writer is replaced by
  an in-memory recorder so the capture does not overwrite the operator's OS
  clipboard; the same injected writer path is used by the production command
- Safety check: Context record bytes and checkpoint identities are compared
  before and after provider-backed summaries and all three copy actions

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-context-first-entry.png` | Launch | Readable Context picker owns initial focus | None |
| `02-descendants-above-context.png` | `Shift-Tab` | Range is immediately above Context and retains `BOTH` | None |
| `03-empty-summary-run-action.png` | `Tab` ×2 | Empty Summary owns `RUN SUMMARIZE · ENTER`; it is one forward focus step after Context | None |
| `04-both-results.png` | `Enter` | Direct and recursive typed results replace the empty action in the same frame | None |
| `04a-header-y-complete.png` | `y` | At the shared title, lowercase `y` copies the same complete document as `Y` | None |
| `05-current-summary-copied.png` | `Down` ×2, `y` | Focused current-only Summary is copied and the footer reports success | None |
| `06-descendants-summary-copied.png` | `Down` ×3, `y` | Descendants Summary is copied independently | None |
| `07-complete-summary-copied.png` | `Y` | Both labelled Summary views are copied as one complete document | None |
| `08-read-only-copy-verification.png` | `Q` | Four projections, Context bytes, and checkpoints are verified | None |
| `09-current-only-option.png` | New launch, `Shift-Tab`, `Right` | `THIS CONTEXT ONLY` is independently selectable | None |
| `10-descendants-option.png` | `Right` | `INCLUDE DESCENDANTS` is independently selectable | None |
| `11-cancel-before-execution.png` | `Q` | Closing setup publishes no result and executes no request | None |
| `12-plain-direct-compatibility.png` | Separate `--plain` launch | Scripted default remains the established direct result | None |

`y` copies the scope containing the focused Summary section. The shared
title/status belongs to the complete document, so lowercase `y` and uppercase
`Y` are identical there. `Y` copies every available labelled scope from any
focus. Neither action creates MemCommit's structured,
mutation-capable clipboard stage.

# Summarize Run-first and dual-result workbench capture log

> Historical evidence for the Run-first topology. The Context-first workbench
> supersedes it under `mem-summarize-context-first-workbench-20260813/`.

This ordered set records the three-way Summarize range and dual-result Viewer.
It supersedes the earlier two-way picker evidence under
`mem-summarize-workbench-20260813/`.

## Reproduction frame

- Command: `python docs/screenshots/mem-summarize-both-workbench-20260813/capture.py`
- TUI command: `mem summarize task-1/participant --tui`
- Plain compatibility command: `mem summarize task-1/participant --plain`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Initial TUI range: `BOTH`; explicit `-d` and `-r` retain their individual
  initial selections
- PTY: `180` columns × `52` rows, `TERM=xterm-256color`, true color,
  `NO_COLOR` unset
- Safety check: Context record bytes and checkpoint identities are compared
  before and after both provider-backed summaries

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-run-first-entry.png` | Launch | `RUN SUMMARIZE` appears above the Context box and owns initial focus | None |
| `02-context-focused.png` | `Tab` | Readable Context picker owns focus | None |
| `03-both-range-focused.png` | `Tab` | `BOTH` is the first and retained range option | None |
| `04-both-results.png` | `S` | Direct and recursive results appear as separate typed sections in one Summary | None |
| `05-recursive-result-focused.png` | `Down` ×7 | The recursive understanding remains independently navigable | None |
| `06-both-read-only-verification.png` | `Q` | Context bytes and checkpoint identities remain unchanged | None |
| `07-current-only-option.png` | New launch, `Tab`, `Tab`, `Right` | `THIS CONTEXT ONLY` is independently selectable | None |
| `08-descendants-option.png` | `Right` | `INCLUDE DESCENDANTS` is independently selectable | None |
| `09-cancel-before-execution.png` | `Q` | Closing setup publishes no result and executes no request | None |
| `10-plain-direct-compatibility.png` | Separate `--plain` launch | Scripted default remains the established direct result | None |

`BOTH` is two explicit application executions, direct first and recursive
second. The workbench publishes the pair only after both succeed. It does not
derive the direct understanding by trimming the recursive result, and it does
not combine the two source frames into one hidden provider call.

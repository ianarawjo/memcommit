# Trace/Rationale Context-or-Memory browser evidence

This ordered set records the direct Switch-style targeting flow for bare
`mem trace` and `mem rationale`. Context and Memory rows share one tree; Enter
on either row returns one exact target. There is no Recents/session launcher,
range frame, or hidden descendant expansion.

## Environment

- PTY: `180` columns × `52` rows, verified inside every child with
  `os.get_terminal_size()`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- CPR: `PROMPT_TOOLKIT_NO_CPR=1` prevents a recorder limitation from appearing
  as application output
- Store/Profile: isolated temporary `HOME`-equivalent Store per path
- Current Context: `empty` for images 01–02; `notes` for images 03–12
- Invocation: the focused capture imports and invokes the production Trace,
  Rationale, and fixture command entry callables from repository source. This
  avoids coupling this TUI evidence to unrelated root-command imports.
- Provider: Trace connects none. Rationale uses a deterministic capture-only
  provider response after target selection; the browser catalog is not sent.
- Verification: each path hashes all Context files, checkpoints, and the
  current pointer before and after execution. Command-attempt recording is
  disabled for the capture.

## Ordered interaction log

| Image | Exact command and preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-trace-empty-context-browser.png` | `mem trace` with current `empty` | The empty Context is the focused, selectable row; no fake Memory or empty-state detour appears | None |
| `02-trace-empty-cancel-verification.png` | preceding state, then `q` | Trace cancellation returns to the terminal and the read-only digest check passes | None |
| `03-trace-browser-context-focused.png` | `mem trace` with current `notes` | Context `notes` is focused; its direct Memories and lexical child are visible in the same Switch-style tree | None |
| `04-trace-browser-memory-focused.png` | preceding state, then `Down` | The first Memory owns keyboard focus and Enter is labelled `trace Memory`; the Context remains unselected | None |
| `05-trace-memory-result-viewer.png` | preceding state, then `Enter` | The exact selected Memory opens the existing bounded Trace Viewer | None |
| `06-trace-memory-verification.png` | preceding state, then `q` | The Viewer closes and Context/checkpoint/current-pointer hashes remain unchanged | None |
| `07-trace-context-result-viewer.png` | fresh `mem trace`, then `Enter` on focused `notes` | The exact Context opens the Context Lineage Viewer; child content is not folded into the parent subject | None |
| `08-trace-context-verification.png` | preceding state, then `q` | The Context Viewer closes and the read-only digest check passes | None |
| `09-rationale-browser-context-focused.png` | `mem rationale` with current `notes` | Rationale presents the same Context-or-Memory tree and starts on the Context | None |
| `10-rationale-browser-memory-focused.png` | preceding state, then `Down` | The exact Memory is focused and Enter is labelled `explain Memory` | None |
| `11-rationale-memory-result-verification.png` | preceding state, then `Enter` | The compact Memory Rationale receipt is printed, followed by the unchanged-state check | None |
| `12-rationale-context-result-verification.png` | fresh `mem rationale`, then `Enter` on focused `notes` | The exact Context Rationale is printed, followed by the unchanged-state check | None |

The fixture creates `notes`, two direct Memories, and `notes/child` with one
Memory. One root Memory has an Add→Edit history so the same selected row can
prove exact-Memory routing. Each child process generates fresh UIDs and resolves
the target from the isolated Store rather than hard-coding it.

## Reproduction

```bash
PYTHONPATH=src python agent-records/docs/screenshots/trace-rationale-context-memory-browser-20260831/capture.py
```

The script fails if the raw PTY stream lacks foreground/background ANSI color,
if old `RECENT`, `RANGE`, `INCLUDE DESCENDANTS`, or `CONTEXT NOT SELECTABLE`
language reappears, if either target kind fails to produce its expected report,
or if any Context/checkpoint/current-pointer digest changes.

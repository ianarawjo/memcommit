# Static `mem log` capture log

This ordered capture verifies that Log remains a terminal-independent report
while its trusted action tokens use the shared semantic palette and every
compact identifier names its UID namespace. Bare Log prints only the current
Context; an explicit target prints only that Context. Neither route opens a
full-screen application or waits for key input.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/mem-static-log-20260820/capture.py`
- Commands under observation: exact `mem log` and
  `mem log --context archive`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated fixture store; `notes` at capture
- PTY: `180` columns × `52` rows, verified by live `stty size`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Store isolation: a temporary `mem` entrypoint patches only
  `memcommit.store.STORE_DIR` before loading the real CLI; no personal Profile
  or Context content is read
- Renderer: actual color-preserving PTY bytes replayed through `pyte` and drawn
  on the full `1832×1124` Menlo terminal canvas. Raw `.typescript` and plain
  `.txt` evidence are retained beside each PNG.
- Interaction: no keys or text are sent after either command starts
- Color verification: the current-Context stream must contain the canonical
  true-color ANSI foregrounds for Create/Add, Embed, Edit, Remove, Undo, Redo,
  and manual History; Memory, Receipt, and Source roles retain their own typed
  presentation

## Ordered evidence

| Image | Exact command/state | Visible result | Durable mutation |
| --- | --- | --- | --- |
| `01-current-context-static-log.png` | `mem log`; current `notes` | `DIRECT COMMANDS` report with role-labelled Checkpoint, Memory, Receipt, Source, and Context prefixes plus the semantic action colors; no picker chrome or key footer | None |
| `02-explicit-context-static-log.png` | `mem log --context archive`; current remains `notes` | Only the `archive` direct-command report, followed by the unchanged-current receipt | None |

The setup commands create only the temporary fixture store before capture. The
captured Log commands are read-only. Each raw stream contains ANSI bold styling
and excludes the alternate-screen sequence used by full-screen TUIs. The
fixture intentionally leaves mixed `atomize` out of the semantic action set;
the real current-store verification likewise shows it in neutral text.
Branch fixtures are covered separately by the typed History browser evidence,
where `INHERITED HISTORY` is rendered after direct commands.

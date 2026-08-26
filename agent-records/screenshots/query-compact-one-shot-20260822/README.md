# Compact one-shot Query capture

These images record the representative ordinary-Context path after Query's
Saved Transcripts, session name, and To Do surfaces were removed. The screen
uses the shared compact exact-Context row and opens the frozen readable tree
only through `[ BROWSE ]`.

- Command: `python agent-records/screenshots/query-compact-one-shot-20260822/capture.py`
- PTY: `180` columns × `52` rows, verified by the child as `PTY 180 52`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed;
  raw streams contain foreground and background ANSI styles
- Profile: isolated local capture fixture; current Context `task-1`
- Provider: injected deterministic provider through the production ordinary
  Query application/runtime boundary
- Durable boundary: fixture Contexts are created before capture; every
  interaction below is read-only, and the final snapshot verifies identical
  Source files and no `query-sessions/` directory

| Image | Preceding keys/text | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-compact-scope.png` | launch | Question initially focused; compact Context, Browse, range, and embeds controls; no Saved Transcripts or To Do | none |
| `02-source-browse-open.png` | `Tab` ×4, `Enter` | transient frozen readable Context tree open | none |
| `03-source-row-focused.png` | `Down` ×2 | a Browse row is focused without changing Source content | none |
| `04-source-browse-closed.png` | `Escape`, `/` | tree hidden; compact Scope restored and Question focused | none |
| `05-question-entered.png` | `What changes during construction?` | exact question draft visible before execution | none |
| `06-one-shot-querying.png` | `Enter` | one provider turn in progress; inputs locked | none |
| `07-answer-ready.png` | provider returns | typed answer and References visible in Answer | none |
| `08-reference-focused.png` | `Down` | first typed Reference owns blue focus | none |
| `09-read-only-verification.png` | `Ctrl-C` | child receipt proves one request/call, unchanged Source files, no Query-session directory | none |
| `10-query-view-source-selected.png` | new child; `Tab` ×2, `Right` | typed Query View Source mode selected without execution | none |
| `11-query-view-browse-open.png` | `Tab` ×2, `Enter` | transient authorized public Query View catalog open | none |
| `12-query-view-row-focused.png` | `Down` | second authorized public View focused | none |
| `13-query-view-no-disclosure-verification.png` | `Ctrl-C` | child receipt proves Browse made no ordinary/granted runner call and opened no concealed Source | none |

Each `.png` is rendered from its matching real PTY `.typescript`; the `.txt`
file is the corresponding 180×52 terminal canvas for text inspection.

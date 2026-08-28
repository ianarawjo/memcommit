# Query TUI interface and semantic clipboard capture log

This ordered set records the Query workbench after its ownership moved from
`memcommit.adapters.console.commands` to `memcommit.adapters.interfaces.tui.operations.query`. It covers
entry, question input, provider completion, the typed Answer/Reference focus
sequence, focused `y` copy, complete-document `Y` copy, the nonfatal clipboard
failure boundary, and read-only verification.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/query-tui-interface-20260815/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: no store or Profile is opened; the child uses a
  synthetic Task 1-shaped readable catalog and a process-local `task-1` marker
- PTY: `180` columns x `52` rows; each child prints and verifies the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832x1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the capture helper requires ANSI foreground and blue
  focused-control background styles before succeeding.
- Clipboard provenance: the production workbench, typed projections, and real
  `y`/`Y` bindings run unchanged. A capture-local writer records exact payloads
  in memory and cannot replace the person's macOS clipboard.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-query-entry.png` | Launch Query | Blank writable Question owns focus | None |
| `02-query-question-entered.png` | Type `What changed during construction?` | Lowercase input remains ordinary text | None |
| `03-query-answer-body-focused.png` | `Enter` | Frozen Query completes; Answer body is the first typed focus stop | None |
| `04-query-answer-body-copied.png` | `y` | Footer confirms only the Answer body was copied | None |
| `05-query-reference-focused.png` | `Down` | Compact Reference row 1 owns the shared blue focus; its own Context remains visible and the prior receipt clears | None |
| `06-query-reference-copied.png` | `y` | Footer confirms the complete one-line focused Reference row was copied | None |
| `07-query-complete-answer-copied.png` | `Y` | Footer confirms the body-plus-References document was copied | None |
| `08-query-read-only-verification.png` | `Ctrl-C` | Three distinct payloads are printed; no session or Source changed | None |
| `09-query-copy-failed.png` | Launch failure Query, type question, `Enter`, `y` | Adapter failure stays in Answer as `COPY FAILED` | None |
| `10-query-failure-verification.png` | `Ctrl-C` | The failed copy changed neither clipboard text nor Query state | None |

The complete copy comes from the typed `SearchAnswerReferenceDocument`, not from
reparsing rendered terminal text. It therefore excludes viewport wrapping,
focus styles, and any mutation-oriented structured clipboard stage.
Each Reference payload is `[N] content — UID prefix, Context alias`; adjacent
rows do not share or inherit a Source heading.

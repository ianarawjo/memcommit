# Query and Find semantic clipboard capture log

This ordered set records focused `y` copy and uppercase `Y` complete-document
copy on Query's read-only `ANSWER` Surface and Find's read-only `RESULTS`
Surface. It also records the shared nonfatal clipboard-failure boundary.

## Reproduction frame

- Command: `python agent-records/screenshots/query-find-clipboard-20260813/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: no store or Profile is opened; the children use a
  synthetic Task 1-shaped readable catalog and a process-local `task-1` current
  marker
- PTY: `180` columns × `52` rows; each child prints and verifies the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the capture helper requires the expected ANSI foreground
  and blue focused-control background styles before succeeding.
- Clipboard provenance: the production workbenches, semantic projections, and
  real `y`/`Y` bindings run unchanged. A capture-local writer records exact
  payloads in memory so this evidence run cannot replace the person's macOS
  clipboard. Production still uses the existing `/usr/bin/pbcopy` adapter.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-query-entry.png` | Launch Query | Blank writable Question owns focus; no provider turn has run | None |
| `02-query-question-entered.png` | Type `What changed during construction?` | The question contains lowercase characters normally; no copy binding fires in input | None |
| `03-query-answer-body-focused.png` | `Enter` | Frozen Query completes; Answer body is the first typed focus stop | None |
| `04-query-answer-body-copied.png` | `y` | Footer confirms only the Answer body was copied | None |
| `05-query-reference-focused.png` | `Down` | Compact Reference row 1 owns the shared blue focus with its exact Context visible; prior receipt clears | None |
| `06-query-reference-copied.png` | `y` | Footer confirms the complete one-line focused Reference row was copied | None |
| `07-query-complete-answer-copied.png` | `Y` | Footer confirms the complete body-plus-References document was copied | None |
| `08-query-read-only-verification.png` | `Ctrl-C` | Three distinct payloads are printed; no session or Source was changed | None |
| `09-query-copy-failed.png` | Launch failure Query, type question, `Enter`, `y` | Simulated adapter failure stays in Answer as `COPY FAILED` | None |
| `10-query-failure-verification.png` | `Ctrl-C` | The failed attempt did not replace clipboard text or mutate Query state | None |
| `11-find-entry.png` | Launch Find | Blank writable Search owns focus; no search has run | None |
| `12-find-query-entered.png` | Type `construction parking` | Query text is ordinary writable input | None |
| `13-find-first-result-focused.png` | `Enter` | Frozen search completes with result 1 focused and Save As still untouched | None |
| `14-find-first-result-copied.png` | `y` | Footer confirms only ranked result 1 was copied | None |
| `15-find-second-result-focused.png` | `Down` | Result 2 owns focus; prior receipt clears | None |
| `16-find-second-result-copied.png` | `y` | Footer confirms only ranked result 2 was copied | None |
| `17-find-complete-results-copied.png` | `Y` | Footer confirms the complete two-result ranked set was copied | None |
| `18-find-read-only-verification.png` | `Ctrl-C` | Focused payloads are distinct, complete payload contains both, and no Context was created | None |

Query's complete copy comes from its typed `FindAnswerReferenceDocument`, not
from reparsing rendered terminal text. Find's complete copy uses its stable
grouped renderer over the frozen response. Neither includes viewport wrapping,
focus styles, checkboxes, or a structured mutation clipboard stage.
Query repeats provenance in every compact `[N] content — UID prefix, Context
alias` row because consecutive References may come from different Sources.

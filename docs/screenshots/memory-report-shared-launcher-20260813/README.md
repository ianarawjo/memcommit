# Shared Trace/Rationale launcher capture log

This ordered evidence set records the common read-only launcher used by bare
`mem trace` and `mem rationale`. Both operations begin with the same Context
range control and the same Context/Memory tree. Each Memory row exposes the
number of distinct recorded operations retained for its Log/Trace lineage.

## Reproduction frame

- Command: `python docs/screenshots/memory-report-shared-launcher-20260813/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: a capture-local store with current Context `demo`,
  empty at the root, and one Memory under `demo/child`
- Fixture history: add `First wording`, edit to `Second wording`, then edit to
  `Final wording used by both reports`; the row therefore shows
  `3 recorded changes`
- PTY: `180` columns × `52` rows; the child prints and verifies the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the capture requires the shared light-blue ANSI focus
  style, heavy focused-frame glyphs, and the reverse-video row focus before
  succeeding.
- Provider boundary: the Rationale evidence invokes recorded-only mode inside
  the child so the shared launcher and result can be verified deterministically
  without any provider connection.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-trace-exact-entry.png` | Launch bare Trace | Shared `RANGE` frame has the blue heavy focus border on `THIS CONTEXT ONLY`; exact root has no Memory | None |
| `02-trace-descendants.png` | `Right` | `INCLUDE DESCENDANTS` is selected inside the same focused frame and the child Memory becomes visible | None |
| `03-trace-memory-focused.png` | `Tab`, `Down`, `Down` | Focus moves through the common Surface controller to the blue heavy `CONTEXTS & MEMORIES` frame; the child row shows `3 recorded changes` | None |
| `04-trace-result.png` | `Enter` | Trace opens the shared Log temporal `ITEMS + VIEWER` result | None |
| `05-trace-verification.png` | `q` | Child reports the selected UID and unchanged store content | None |
| `06-rationale-exact-entry.png` | Launch bare Rationale | The same shared framed launcher starts at exact range | None |
| `07-rationale-descendants.png` | `Right` | The same descendant range exposes the same Memory | None |
| `08-rationale-memory-focused.png` | `Tab`, `Down`, `Down` | The same common target frame owns focus and the Memory row shows the same `3 recorded changes` | None |
| `09-rationale-result.png` | `Enter` | Rationale opens its complete common read-only Viewer report | None |
| `10-rationale-verification.png` | `q` | Child reports the selected UID and unchanged store content | None |

The launcher reuses `build_focused_frame`, `build_tui_frame`, the service theme,
and `SurfaceFocusController`; it does not define Trace- or Rationale-specific
frame chrome. It controls target discovery only. Trace subsequently opens
the temporal History explorer, while Rationale opens its explanatory report;
those result adapters remain intentionally different because their documents
have different semantics.

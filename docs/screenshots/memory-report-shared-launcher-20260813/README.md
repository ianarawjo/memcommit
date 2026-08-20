# Shared Trace/Rationale launcher capture log

This ordered evidence set records the common read-only target launcher used by
bare `mem trace` and `mem rationale`. Both operations open the current
`notes` Context's Memories immediately, without a preceding Profile/local
Context location selector. The same screen retains the exact/subtree range
control so descendants remain an explicit choice. Pressing Enter on a Context
leaves the selector open and shows the red `CONTEXT NOT SELECTABLE` receipt;
Left/Right retain Context-tree navigation, and only a Memory row completes the
selection. Each Memory row exposes the
number of distinct recorded operations retained for its Log/Trace lineage.
The fixture also retains a removed Memory so both lifecycle forms are visible.
The compact row uses separate `[UID][rN]` badges; the default current state is
omitted and the retained-only entry renders `[historical][UID][r2]`.
Only `[historical]` uses muted warm taupe `#c9ad93`; the UID, revision, and
Memory content retain the shared lavender, while row focus remains blue.
The recorded PTY quantizes that configured color to xterm-256 color `180`.

## Reproduction frame

- Command: `python docs/screenshots/memory-report-shared-launcher-20260813/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: a capture-local store with current Context `notes`;
  an unrelated `other-empty` root proves the command does not require a
  location choice, and `notes/child` proves range expansion remains available
- Fixture history: add `First wording`, edit to `Second wording`, then edit to
  `Final wording used by both reports`; the row therefore shows
  `[UID][r3]`. Add then remove `Retained historical wording`; its row shows
  `[historical][UID][r2]`.
- PTY: `180` columns × `52` rows; the child prints and verifies the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the capture requires the shared light-blue ANSI focus
  style, heavy focused-frame glyphs, reverse-video row focus, the exact
  warm-taupe historical badge, and the shared red validation-error role before
  succeeding.
- Provider boundary: the Rationale evidence invokes recorded-only mode inside
  the child so the shared launcher and result can be verified deterministically
  without any provider connection.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-trace-current-memories-entry.png` | Launch bare Trace | `TRACE · SELECT A MEMORY · notes` opens immediately; `THIS CONTEXT ONLY` shows current and historical direct Memories | None |
| `02-trace-context-rejected.png` | `Tab`, `Enter` on `notes` | Context remains a navigation row; red `CONTEXT NOT SELECTABLE · Select an exact Memory row` appears and no target is returned | None |
| `03-trace-descendants.png` | `Shift-Tab`, `Right` | `INCLUDE DESCENDANTS` additionally reveals `notes/child` and its Memory | None |
| `04-trace-memory-focused.png` | `Tab`, `Down` × 2 | The retained-only `[historical][UID][r2]` row is focused | None |
| `05-trace-result.png` | `Enter` | Trace opens the shared Log temporal result | None |
| `06-trace-verification.png` | `q` | Child reports `CURRENT notes` and unchanged store content | None |
| `07-rationale-current-memories-entry.png` | Launch bare recorded-only Rationale | The same current-root target launcher opens directly | None |
| `08-rationale-context-rejected.png` | `Tab`, `Enter` on `notes` | The same red rejection preserves the exact-Memory target boundary | None |
| `09-rationale-descendants.png` | `Shift-Tab`, `Right` | The descendant range exposes the child Memory | None |
| `10-rationale-memory-focused.png` | `Tab`, `Down` × 2 | The same target frame focuses the historical row | None |
| `11-rationale-result.png` | `Enter` | Rationale opens its complete read-only Viewer report | None |
| `12-rationale-verification.png` | `q` | Child reports `CURRENT notes` and unchanged store content | None |

The target launcher reuses `build_focused_frame`, `build_tui_frame`, the service
theme, and `SurfaceFocusController`; it does not define Trace- or
Rationale-specific frame chrome. It controls target discovery only. Trace subsequently opens
the temporal History explorer, while Rationale opens its explanatory report;
those result adapters remain intentionally different because their documents
have different semantics.

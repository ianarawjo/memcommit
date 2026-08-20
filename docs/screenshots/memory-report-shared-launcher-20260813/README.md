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
The compact row uses separate `[UID] [rN]` badges; the default current state is
omitted and the retained-only entry renders `[historical][UID][r3]`.
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
  `[UID] [r3]`. Add `Retained historical wording`, edit it to `Revised
  historical wording`, then remove it; its row shows `[historical] [UID] [r3]`.
- PTY: `180` columns × `52` rows; the child prints and verifies the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the capture requires the shared light-blue ANSI focus
  style, heavy focused-frame glyphs, reverse-video row focus, the exact
  warm-taupe historical badge, lavender Memory objects, the shared red ERROR
  role for rejected Context selection, and semantic create/remove diff tokens
  before succeeding.
- Provider boundary: the Rationale evidence invokes recorded-only mode inside
  the child so the shared launcher and result can be verified deterministically
  without any provider connection.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-trace-current-memories-entry.png` | Launch bare Trace | `TRACE · SELECT A MEMORY · notes` opens immediately; `THIS CONTEXT ONLY` shows current and historical direct Memories | None |
| `02-trace-context-rejected.png` | `Tab`, `Enter` on `notes` | Context remains a navigation row; red `CONTEXT NOT SELECTABLE · Select an exact Memory row` appears and no target is returned | None |
| `03-trace-descendants.png` | `Shift-Tab`, `Right` | `INCLUDE DESCENDANTS` additionally reveals `notes/child` and its Memory | None |
| `04-trace-memory-focused.png` | `Tab`, `Down` × 2 | The retained-only `[historical] [UID] [r3]` row is focused | None |
| `05-trace-result.png` | `Enter` | Trace opens one compact continuous document sized to its content: direct Add/Remove are single Log-style rows, while Edit ends its header at the timestamp and lets the inline `− before` / `+ after` diff explain the change; no repeated generic summary/effect/evidence suffix, NOW/ORIGIN bands, Items surface, or empty full-screen canvas remain | None |
| `06-trace-verification.png` | `q` | Child reports `CURRENT notes` and unchanged store content | None |
| `07-rationale-current-memories-entry.png` | Launch bare recorded-only Rationale | The same current-root target launcher opens directly | None |
| `08-rationale-context-rejected.png` | `Tab`, `Enter` on `notes` | The same red rejection preserves the exact-Memory target boundary | None |
| `09-rationale-descendants.png` | `Shift-Tab`, `Right` | The descendant range exposes the child Memory | None |
| `10-rationale-memory-focused.png` | `Tab`, `Down` × 2 | The same target frame focuses the historical `[r3]` row | None |
| `11-rationale-result.png` | `Enter` | Rationale opens its complete read-only Viewer report | None |
| `12-rationale-verification.png` | `q` | Child reports `CURRENT notes` and unchanged store content | None |

The target launcher reuses `build_focused_frame`, `build_tui_frame`, the service
theme, and `SurfaceFocusController`; it does not define Trace- or
Rationale-specific frame chrome. It controls target discovery only. Trace
subsequently opens its vertical lineage document in the common read-only
Viewer, while Rationale opens its explanatory report there; the documents
remain intentionally different because their semantics differ, but neither
adds a second result-navigation surface.

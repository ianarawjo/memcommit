# Shared Trace/Rationale launcher capture log

This ordered evidence set records the common read-only launcher used by bare
`mem trace` and `mem rationale`. Both operations begin with a Profile/local
Context location selector even though the current Context is empty, then open
the same Context range control and Context/Memory tree for the chosen nonempty
location. Each Memory row exposes the
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
- Profile/current Context: a capture-local store with current Context
  `empty-current`; a separate `notes` root has current plus historical-only
  lineage entries under `notes/child`
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
  style, heavy focused-frame glyphs, reverse-video row focus, and the exact
  warm-taupe historical badge before succeeding.
- Provider boundary: the Rationale evidence invokes recorded-only mode inside
  the child so the shared launcher and result can be verified deterministically
  without any provider connection.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-trace-context-entry.png` | Launch bare Trace | `TRACE · SELECT A CONTEXT · LOCAL CONTEXTS` opens on empty current `empty-current` | None |
| `02-trace-context-target.png` | `Down` | `notes` is focused without changing global current Context | None |
| `03-trace-exact-entry.png` | `Enter` | Scoped `RANGE` starts at `THIS CONTEXT ONLY`; exact `notes` root has no Memory | None |
| `04-trace-descendants.png` | `Right` | `INCLUDE DESCENDANTS` reveals the child Memories | None |
| `05-trace-memory-focused.png` | `Tab`, `Down` × 3 | The retained-only `[historical][UID][r2]` row is focused | None |
| `06-trace-result.png` | `Enter` | Trace opens the shared Log temporal result | None |
| `07-trace-verification.png` | `q` | Child reports `CURRENT empty-current` and unchanged store content | None |
| `08-rationale-context-entry.png` | Launch bare Rationale | `RATIONALE · SELECT A CONTEXT · PROFILE` opens on the same empty current Context | None |
| `09-rationale-context-target.png` | `Down` | `notes` is focused process-locally | None |
| `10-rationale-exact-entry.png` | `Enter` | The same scoped target launcher starts at exact range | None |
| `11-rationale-descendants.png` | `Right` | The descendant range exposes the child Memories | None |
| `12-rationale-memory-focused.png` | `Tab`, `Down` × 3 | The same target frame focuses the historical row | None |
| `13-rationale-result.png` | `Enter` | Rationale opens its complete read-only Viewer report | None |
| `14-rationale-verification.png` | `q` | Child reports `CURRENT empty-current` and unchanged store content | None |

The location stage reuses the same Context selector as Log and Switch. The
scoped launcher reuses `build_focused_frame`, `build_tui_frame`, the service
theme, and `SurfaceFocusController`; it does not define Trace- or
Rationale-specific frame chrome. It controls target discovery only. Trace subsequently opens
the temporal History explorer, while Rationale opens its explanatory report;
those result adapters remain intentionally different because their documents
have different semantics.

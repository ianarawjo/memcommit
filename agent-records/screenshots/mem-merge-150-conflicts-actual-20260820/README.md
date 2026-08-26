# Actual 150-conflict Merge evidence

- Capture command: `python agent-records/screenshots/mem-merge-150-conflicts-actual-20260820/capture.py`
- PTY: `180×52`, true color, `NO_COLOR` removed
- Store: fresh isolated temporary `.mem` root
- Preconditions: Source and Target each contain 150 Memories with the same 150
  UIDs and different complete bodies
- Merge route: bare interactive `mem merge`; direct Source `source` into current
  Target `target`

| # | State | Preceding action | Evidence | Durable effect |
| --- | --- | --- | --- | --- |
| 01 | First conflict page | Continue from Merge setup | Actual planner reports `MERGE REVIEW · 150 conflicts`; every visible row starts checked on Target; the separate Controls frame derives and checks `KEEP ALL TARGET` | None |
| 02 | Direct Apply focus | `Tab` | One key crosses from the scrollable Conflicts frame directly to `APPLY · READY`; no conflict traversal occurs | None |
| 03 | Middle conflict page | `Shift-Tab`, `PageDown` | Conflict focus and its independent viewport return without changing any decision | None |
| 04 | Final conflict | `PageDown`, `PageDown` | Conflict 150 is reachable while the separate Controls frame remains visible | None |
| 05 | Direct Apply focus from the bottom | `Tab` | The same one-key frame transition works after scrolling to conflict 150 | None |
| 06 | Bulk decision focused | `Up` | The Controls frame distinguishes the staged-value `BULK DECISION` from the mutation boundary `APPLY` | None |
| 07 | All Source staged | `Right`, `Enter` | All 150 rows are checked on Source; the derived bulk light moves automatically to `TAKE ALL SOURCE`; focus returns to Apply | None |
| 08 | Exact review | `Enter` | Exact frozen command is `--take-source-all`; counts say `KEEP TARGET 0 · TAKE SOURCE 150`; the Controls frame exposes the exact Apply action | None |
| 09 | Applied receipt | `Enter` | Receipt reports `TOOK SOURCE · 150`, Target changed, and one checkpoint; Controls now exposes Close | All 150 Target bodies replaced atomically |
| 10 | Read-only verification | Close receipt | Target has 150 Memories; every first-through-last body equals Source; one checkpoint exists | None beyond 09 |

The conflict objects are produced by the real Merge planner. The fixture only
creates the two divergent Contexts; it does not construct a synthetic
`FrozenMergePlan` or inject conflicts into the interface.

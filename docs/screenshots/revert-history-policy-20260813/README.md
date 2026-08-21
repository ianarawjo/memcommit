# Revert location and history-policy capture log

> Historical pre-change evidence. The current Revert entry and Viewer are
> refreshed under `docs/screenshots/revert-revision-result-20260821/`: bare
> Revert now opens the current Context directly and shows a complete revision
> result instead of `RESTORE IMPACT`. The policy and Apply mechanics recorded
> here remain background design history, not the current end-to-end screen.

This ordered snapshot set records the location-first Revert flow, its safe
empty state, the in-TUI `DISCARD NEWER`/`KEEP ALL` choice, exact Apply, and
read-only verification.

## Reproduction frame

- Command: `python docs/screenshots/revert-history-policy-20260813/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: an isolated temporary store; current is
  `task-1/participant`, which deliberately has no checkpoints; the independently
  selectable `task-1/recovery` has a proven Atomize-attributed creation
  boundary, an Atomize checkpoint, and a newer Add checkpoint
- Provider provenance: no provider is opened; every target and diff is derived
  from exact local checkpoint records
- PTY: `180` columns × `52` rows; each child sets and reads the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: actual ANSI PTY streams replayed through `pyte` and drawn on a full
  Menlo terminal canvas; raw `.typescript` and plain `.txt` evidence remain
  beside each PNG
- Color verification: the capture requires foreground and background ANSI
  styles before succeeding

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-context-picker-empty-current.png` | Launch bare `mem revert` equivalent | `REVERT · SELECT A CONTEXT`; empty current Context is the initial tree row | None |
| `02-empty-history-view.png` | `Enter` | Explicit `0/0` empty History view; no checkpoint can be applied | None |
| `03-created-atomize-boundary.png` | `Backspace`, `Down`, `Right` | Expanded local Context folds its correlated creation-time Atomize into one `[created] [atomize]` row; the later `[add]` remains separate | None |
| `04-recovery-checkpoints.png` | `Enter` | The selected Context opens with its three exact retained checkpoints | None |
| `05-target-impact-preview.png` | `Down` × 2 | Init checkpoint is targeted; Viewer shows current-to-target removal impact | None |
| `06-discard-newer-policy.png` | `Enter` | Exact target is checked and the default `DISCARD NEWER` history policy owns focus | None |
| `07-keep-all-policy.png` | `Right` | `KEEP ALL` is checked; its meaning is visible before approval | None |
| `08-exact-apply.png` | `Enter` | Apply repeats the target checkpoint and `KEEP ALL CHECKPOINTS` policy | None |
| `09-success-receipt.png` | `Enter` | Revert receipt reports the exact restored state and recovery routes | Revert writes the restored Context and pre-Revert recovery checkpoint |
| `10-read-only-verification.png` | Launch verification child | Target is empty, all three original checkpoint UIDs remain, and current still points to `task-1/participant` | None |

The capture uses the production Context tree, History picker, restore-impact
renderer, policy control, store locks, Revert path, and receipt. Its temporary
store is deleted after verification.

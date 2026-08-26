# Recursive Checkpoint global Revert capture log

This ordered snapshot set proves that the UID printed by `checkpoint
--recursive` is a physical root checkpoint UID, that the same UID is staged in
Revert's exact command boundary, and that one Revert and one Undo move both
Contexts together. The pre-Apply Viewer and grouped receipt both make the
complete membership explicit.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/recursive-checkpoint-global-revert-20260823/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated temporary store; current is
  `demo/recovery`, with lexical child `demo/recovery/child`
- Provider provenance: no provider is opened; the catalog, membership, diffs,
  Revert, and Undo are derived from local checkpoint records
- PTY: `180` columns x `52` rows; every child sets and prints the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: actual ANSI PTY streams replayed through `pyte` and drawn on a
  full Menlo terminal canvas; raw `.typescript` and plain `.txt` evidence are
  stored beside each PNG
- Color verification: capture fails unless foreground and background ANSI
  styles occur in the recorded streams

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-recursive-checkpoint-receipt.png` | Run `checkpoint --recursive` equivalent | One canonical UID plus an exact `mem revert UID --keep` command | Two physical checkpoints are atomically written |
| `02-history-entry.png` | Add one newer Memory to each Context; launch bare `mem revert` equivalent | Current Context History and Viewer | Setup mutations precede launch; none in this screen |
| `03-recursive-unit-focused.png` | `Down` to the recursive root checkpoint | Exact physical root checkpoint and its revision detail | None |
| `04-complete-unit-command-review.png` | `Enter` | Exact command review stages the canonical UID and names both Context/member checkpoints before Apply | None |
| `05-keep-all-policy-review.png` | `Escape` | `KEEP ALL` is explicitly focused before approval | None |
| `06-group-revert-receipt.png` | `Enter`, `Enter` | One grouped Revert receipt lists both affected Contexts and one Undo route | Both Contexts return to their baseline snapshots |
| `07-read-only-revert-verification.png` | Launch verification child | Both Contexts contain only baseline Memories | None |
| `08-group-undo-receipt.png` | Run `mem undo` equivalent | One command-unit Undo receipt lists both Contexts | Both pre-Revert snapshots are restored together |
| `09-read-only-undo-verification.png` | Launch verification child | Both Contexts again contain their newer Memories | None |

The temporary store is deleted after the final verification.

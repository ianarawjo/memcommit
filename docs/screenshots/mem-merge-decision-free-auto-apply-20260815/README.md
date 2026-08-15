# Merge decision-free auto-apply capture log

This ordered set verifies that bare interactive Merge follows the common
ownership-aware application policy. A conflict-free local frozen plan skips
duplicate plan review, but still crosses the normal application boundary and
records the complete checkpoint required by Undo/Redo. Required conflicts and
granted-authority mutation remain review boundaries.

## Reproduction frame

- Command: `python docs/screenshots/mem-merge-decision-free-auto-apply-20260815/capture.py`
- Command under capture: bare `mem merge` through the real Typer command
  adapter, plus the real `mem undo` and `mem redo` adapters
- Store: isolated temporary local Profile; current Target `target`, readable
  Source `source`
- PTY: 180 columns × 52 rows, verified by the child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: real cumulative ANSI streams replayed through `pyte` at the full
  terminal canvas; raw `.typescript` and plain `.txt` files accompany each PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-decision-free-setup.png` | Launch bare `mem merge` | Source/current-Target setup owns focus and states that required conflicts are reviewed before Apply | None |
| `02-conditional-auto-apply-action.png` | `Tab` | Setup action explicitly says classification may Apply when no decision is required | None |
| `03-auto-applied-checkpoint-receipt.png` | `Enter` | Conflict-free addition applies without opening `REVIEW FROZEN PLAN`; plain receipt and Store verification show one checkpoint | Source Memory added; one Merge checkpoint |
| `04-noop-auto-applied-checkpoint.png` | Separate identical Source/Target launch; `Tab`, `Enter` | Verified zero-delta receipt returns directly, with one checkpoint and no frozen-plan review | One zero-delta Merge checkpoint |
| `05-noop-undo-receipt.png` | `Enter` at capture pause | Real Undo consumes that exact no-op command unit and reports no direct Context changes | Merge command unit moved to Redo |
| `06-noop-redo-receipt.png` | `Enter` at capture pause | Real Redo restores the same no-op Merge command boundary | Merge command unit restored |
| `07-auto-apply-failure-no-checkpoint.png` | Separate addition launch; `Tab`, `Enter`; injected failure before persistence | Auto-apply reports failure; Store verification shows no copied UID and zero checkpoints | None |

The bypass removes only redundant review. It does not bypass plan freezing,
authority checks, freshness/CAS revalidation, atomic persistence, receipt
rendering, checkpoint creation, or recovery.

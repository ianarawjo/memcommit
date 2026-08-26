# Historical Profile-wide List and Context browser capture log

> Superseded on 2026-08-20. List and Contexts now print terminal-independent
> reports; bare Switch owns top-level interactive Context navigation. This
> ordered set remains as evidence of the rejected Profile-wide browser
> experiment. See
> [`context-listing-design-rationale.md`](../../context-listing-design-rationale.md).

This ordered capture verifies that interactive List and Context browsing use
the complete Profile catalog used by Switch. A supplied or current Context is
the initial row, not a namespace crop boundary.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/profile-wide-list-contexts-20260814/capture.py`
- Commands under observation: `mem list CONTEXT`, `mem list -R CONTEXT`, and
  `mem contexts`
- Working directory: repository root (the absolute capture location may vary)
- Profile/current Context: printed before and after every browser; the script
  asserts that the exact current name is unchanged
- PTY: `180` columns × `52` rows, verified by live `stty size`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas; raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG
- Color verification: the script requires foreground ANSI styling and the
  reverse-video focus style before succeeding

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-list-entry-full-profile.png` | Run `mem list task-2/participant/proposal-workspace` | The exact nested target is focused while Profile roots, ancestors, siblings, and Grant rows remain in one tree | None |
| `02-list-hide-focused-memories.png` | `Left` | The target's direct-item layer closes without changing its Context location | None |
| `03-list-parent-navigation.png` | `Left` | Focus moves to the lexical parent inside the unchanged Profile catalog | None |
| `04-list-close-read-only-verification.png` | `q` | Direct List closes and verifies the current Context is byte-identical | None |
| `05-list-recursive-selected-subtree.png` | Run `mem list -R task-2/advisor1` | The selected readable Grant subtree starts expanded; unrelated Profile roots remain visible but are not eagerly expanded | None |
| `06-list-recursive-close-verification.png` | `q` | Recursive List closes and verifies the current Context is unchanged | None |
| `07-contexts-current-in-full-profile.png` | Run `mem contexts` | The current nested Context is the initial row in the full Profile tree | None |
| `08-contexts-readable-grant-focus.png` | `Down` | Focus reaches a READ-granted row without switching to it | None |
| `09-contexts-query-only-orientation.png` | `Down`, `Down` | Focus reaches the opaque QUERY-only route; it is visible for orientation but not materialized or loadable | None |
| `10-contexts-close-read-only-verification.png` | `q` | Contexts closes and verifies the current Context is unchanged | None |

The TUI catalog breadth does not alter noninteractive List output, clipboard
receipts, or recursive execution scope. QUERY-only rows never enter the Memory
loader, and no browser in this capture publishes a selection receipt.

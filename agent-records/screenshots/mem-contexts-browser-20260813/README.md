# Historical `mem contexts` read-only browser capture log

> Superseded on 2026-08-20. `mem contexts` now prints its stable catalog in
> terminals and pipes alike; bare `mem switch` owns top-level interactive
> Context navigation. These files retain the earlier browser experiment for
> research history and are not current behavioral evidence. See
> [`context-listing-design-rationale.md`](../../context-listing-design-rationale.md).

This ordered capture records the ordinary `mem contexts` command using the
same namespace tree as `mem switch`, while demonstrating that closing the
browser does not change the current Context.

## Reproduction frame

- Command: `python agent-records/screenshots/mem-contexts-browser-20260813/capture.py`
- Command under observation: `mem contexts`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: the active values are printed immediately before
  the browser and again in the final verification frame
- PTY: `180` columns × `52` rows; the script checks the live `stty size`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the script requires foreground ANSI styling and the
  reverse-video focus style before succeeding.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry.png` | Run `mem contexts` | The current Context is focused in the compact shared namespace tree | None |
| `02-row-navigation.png` | `Down` | Focus moves to the next visible Context row without selecting or switching it | None |
| `03-expanded-namespace.png` | `A` | All frozen Context branches are expanded inside the bounded scrolling viewport | None |
| `04-close-read-only-verification.png` | `q` | The browser closes; the active Profile/current Context are printed again and the command verifies the current name is byte-identical to its entry snapshot | None |

No selection receipt, exact approval, provider turn, or success mutation exists
in this flow. Enter and the arrow keys are presentation controls only;
`mem switch` remains the operation that can publish a different current
Context.

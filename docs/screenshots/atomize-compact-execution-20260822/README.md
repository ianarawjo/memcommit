# Atomize compact execution TTY capture

This ordered set records Atomize's execution-only decision route after its
retained analysis and Review report were separated from the applying command.
It also records the shared compact Save Location editor used by Atomize, Meld,
and Sever.

## Reproduction frame

- Command: `python docs/screenshots/atomize-compact-execution-20260822/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified in the child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` unset
- Renderer: the real Prompt Toolkit ANSI stream is replayed through `pyte` on
  a full-size Menlo terminal canvas; raw `.typescript` and plain `.txt`
  evidence accompany every PNG.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-compact-decision.png` | Launch | One Atomize ambiguity decision; typed Recommended reading already checked; retained report absent; exact Output visible | None |
| `02-choice-staged.png` | `Enter` | The Recommended reading remains checked for this execution only | None |
| `03-save-location-input.png` | `Down`, `Down`, `Enter` | Arrow-only navigation opens the shared exact one-line Save Location input | None |
| `04-invalid-location-retained.png` | replace with `wrong/place`, `Enter` | Operation validator rejects the name without closing the editor | None |
| `05-updated-location-compact-return.png` | replace with `atomized/final`, `Enter` | Controller accepts the process-local destination change and returns to the compact decision | Destination plan only |
| `06-applied-receipt.png` | `Down` ×3, `Enter` on separated Apply | Compact Atomize receipt identifies Source, Output, checkpoint, and retained Review route; no second confirmation appears | Output checkpoint (fixture receipt) |
| `07-read-only-verification.png` | `V` | Read-only verification shows the reviewed choice, final Output, zero required findings, and no additional provider turn | None |

Backspace and printable-key behavior inside the exact name field, invalid-name
retention, and the editor/root two-level Escape path are covered separately by
the compact-shell interaction tests.

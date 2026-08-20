# Switch Grant ownership capture log

This ordered capture verifies the shared interactive Context row after the
Grant navigation presentation change. The fixed `GRANT` marker precedes the
public Context name, while the compact usable-capability cluster follows it in
the shared teal access color.

## Reproduction frame

- Command: `python docs/screenshots/mem-switch-grant-ownership-20260820/capture.py`
- Command under observation: exact bare `mem switch`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: active local Profile; `practice/source` at capture
- PTY: `180` columns × `52` rows, set explicitly with `onlcr` and verified by
  live `stty size`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, `NO_COLOR` unset
- Renderer: actual cumulative color-preserving PTY bytes replayed through
  `pyte` and drawn on the full `1832×1124` Menlo terminal canvas. Raw
  `.typescript` and plain `.txt` evidence remain beside every PNG.
- Color verification: the capture requires the exact
  `38;2;139;213;202` truecolor sequence used by the shared capability style.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-switch-entry.png` | Run bare `mem switch` | Current local `practice/source` is focused in the shared Context tree | None |
| `02-grant-prefix-and-capabilities.png` | `Down`, `Right`, `Down×3`, `Right`, `Down` | Task 1 and its granted tree are expanded; `GRANT` precedes public names and the unfocused capability cluster is teal | None |
| `03-cancelled-current-unchanged.png` | `Escape` | Switch prints its cancellation receipt and the shell verifies the exact current Context is unchanged | None |

The flow intentionally cancels. It loads no Memory preview, publishes no
selection, and does not switch or otherwise mutate durable state.

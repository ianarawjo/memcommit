# Static `mem list` and `mem contexts` capture log

This ordered capture shows the implemented terminal-independent command split.
List prints the current Context's direct items; Contexts prints the readable
catalog; neither enters a full-screen application. Bare `mem switch` retains
interactive Profile navigation.

## Reproduction frame

- Command: `python docs/screenshots/mem-static-list-contexts-20260820/capture.py`
- Commands under observation: exact `mem list` and exact `mem contexts`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: active local Profile; `practice/source` at capture
- PTY: `180` columns × `52` rows, verified by live `stty size`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: actual color-preserving PTY bytes replayed through `pyte` and drawn
  on the full `1832×1124` Menlo terminal canvas because direct macOS Terminal
  capture was unavailable to Computer Use. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the raw stream contains ANSI styling, including the
  green current-Context marker and exact `38;2;139;213;202` truecolor sequence
  for the teal capability cluster. `GRANT` itself stays neutral and precedes
  every externally owned public name. Local and granted names share the same
  depth-first public hierarchy as a fully expanded Switch tree; Grant rows are
  no longer collected in a separate trailing block. These static reports
  intentionally use the terminal's default background rather than
  focused-control backgrounds.

## Ordered evidence

| Image | Command/state | Visible result | Durable mutation |
| --- | --- | --- | --- |
| `01-list-static-current-context.png` | `mem list` | `Context: practice/source`, 17 direct Memory rows, then an unchanged-current verification | None |
| `02-contexts-static-catalog-first-page.png` | `mem contexts`, first scrollback page | The static catalog marks `practice/source` as current, then places Task 1's local and granted branches in the shared public hierarchy; no picker chrome or key footer appears | None |
| `03-contexts-grant-capabilities.png` | same `mem contexts` stream, first Grant page | Task 1's neutral `GRANT` rows follow its local branch and precede Task 2; compact `READ`, `QUERY`, `EDIT`, `DELETE`, and `EXPORT` capabilities are teal; `PERMISSIONS` and `ANALYSIS` prose are absent | None |
| `04-contexts-static-catalog-verification.png` | same completed `mem contexts` stream, final page | Catalog ends and the exact current Context is verified unchanged | None |

The second image is rendered from an exact prefix of the full real PTY stream
to represent its first scrollback page. The third replays the exact stream
prefix through the Task 1 local-to-Grant-to-Task 2 transition, preserving the
terminal's real cursor and wrapping state. The complete corresponding stream is
stored as `02-contexts-static-catalog-first-page.full.typescript`; the fourth
image renders the completed stream's final terminal canvas.

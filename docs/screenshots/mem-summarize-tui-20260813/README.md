# Summarize TUI capture log

> Historical evidence for the completed-result-only Viewer. The later
> picker-first workbench supersedes this interaction contract; its refreshed
> evidence is stored under `mem-summarize-workbench-20260813/`.

This ordered set records the first operation adapter built on the extracted
frame and semantic Viewer component hierarchy. `mem summarize` computes one
typed `SummarizeResult`; the console router sends that same result to the TUI
in an interactive terminal or to the established plain renderer when forced.

## Reproduction frame

- Command: `python docs/screenshots/mem-summarize-tui-20260813/capture.py`
- Command under capture: `mem summarize task-1/participant --tui`, invoked
  through the real Typer root with `standalone_mode=False` so the child can
  print a post-close verification line
- Plain verification: `mem summarize task-1/participant --plain`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: Study participant Profile
  `study-20260813T135528Z-d61e7a16`; selected Context
  `task-1/participant`
- Precondition: the selected Context has no direct Memories and no selected
  recursive scope, so the application returns its deterministic empty summary
  without connecting a provider
- PTY: `180` columns × `52` rows; the child prints and verifies the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset;
  command-attempt logging disabled so this read-only evidence run creates no
  audit write
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-viewer-entry.png` | Launch command | Typed `SUMMARY` section owns focus; Viewer shows the exact selected Context | None |
| `02-status-focused.png` | `Down` | `STATUS · READ-ONLY · DIRECT · SOURCES 0` owns focus | None |
| `03-understanding-focused.png` | `Down` | `WHAT MEM UNDERSTOOD` and the provider-free empty summary own focus together | None |
| `04-read-only-close-verification.png` | `q` | The full-screen app closes and the child confirms no Context mutation or checkpoint | None |
| `05-nontui-plain-verification.png` | Separate `--plain` invocation | Established plain Summary output renders without opening the TUI | None |

The captures verify presentation only. Authority, source freezing, empty-frame
provider avoidance, and source revalidation remain in the same application
path and are covered by the focused Summarize tests.

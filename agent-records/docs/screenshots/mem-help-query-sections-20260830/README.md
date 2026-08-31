# `mem help` Retrieve/Answer and Synthesize capture log

This ordered capture verifies the catalog- and application-owned subdivision
of `SEARCH & EXPLAIN`. `RETRIEVE & ANSWER` contains `find`, `search`, and
`query`; `SYNTHESIZE` contains `summarize` and `compare`. The labels describe
the shared affordance instead of restating operation names. Compare no longer
appears in the quality-check family, whose display title is `CHECK & REVIEW`.

## Reproduction frame

- Capture command: `python agent-records/docs/screenshots/mem-help-query-sections-20260830/capture.py`
- Command under observation: `mem help`
- Working directory: repository root
- Profile / current Context: not consulted / not consulted
- PTY: `180` columns × `52` rows; the raw stream includes the verified `stty size`
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: the real cumulative ANSI PTY stream is replayed through `pyte`
  and drawn at the complete terminal-canvas size. Raw `.typescript` and plain
  `.txt` evidence remain beside every PNG.
- Color verification: the capture rejects a stream without foreground and
  background ANSI styles. It verifies that section labels remain neutral while
  the selected operation alone receives the blue focus background.

## Ordered interaction log

| Image | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-by-kind-entry.png` | Run `mem help` | Initial BY KIND Help entry at `BROWSE & NAVIGATE` | None |
| `02-query-focused.png` | `Tab` ×2 | `SEARCH & EXPLAIN` focused with `mem find` under the `RETRIEVE & ANSWER` divider | None |
| `03-summary-focused.png` | `Down` ×3 | Continuous traversal reaches `mem summarize` under `SYNTHESIZE`; both dividers are visible and neutral | None |
| `04-compare-focused.png` | `Down` | The next operation is `mem compare` in the same section | None |
| `05-compare-expanded.png` | `Right` | Compare retains its existing Flow, Execution, Effect, Range, and Forms | None |
| `06-check-review-focused.png` | `Tab` ×3 | The later quality and conformance family is focused as `CHECK & REVIEW`, beginning with `find-duplicates` rather than Compare | None |

After the final capture, `Q` closes the read-only full-screen Help browser with
exit status 0. No state is published by any step.

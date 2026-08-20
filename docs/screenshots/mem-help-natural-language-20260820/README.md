# Natural-language `mem help` live capture log

This ordered set records five real provider-backed invocations of the focused
Help lookup: one match, several matches, a metaphorical request, and an
intentionally unrelated request, plus generic answer/problem-solving language
that may validly resolve to Query. The command uses the pinned
`gpt-5.6-sol` / `none` policy and lets the provider return only zero to three
catalog operation names. Every visible summary and `WHEN` line comes back from
the frozen authored Help catalog rather than from provider-written prose.

## Reproduction frame

- Command: `python docs/screenshots/mem-help-natural-language-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Executable: the installed `mem` entry point resolved from `PATH`
- Profile/current Context: the active Profile provenance is consulted only for
  the Study exact-copy guard; no current Context is consulted
- PTY: `180` columns by `52` rows; every raw stream contains a verified live
  `52 180` result before the canvas is cleared for the final image
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset;
  the unrelated command-attempt log is disabled so these reads do not create
  study evidence
- Renderer: each cumulative real PTY stream is replayed through `pyte` and
  drawn at the full `1832x1124` Menlo/macOS CJK-fallback canvas. Raw
  `.typescript` and terminal-text `.txt` evidence remain beside every PNG.
- Color verification: a separate bare `mem help` control in the same PTY must
  emit both ANSI foreground and focused-control background styles before the
  captures run. Focused lookup output itself intentionally remains stable,
  neutral line-oriented text.

## Ordered invocations

| Image | Exact command | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-single-compare.png` | `mem help "두 Context의 차이를 보고 싶어"` | One compact Compare record: command, authored description, and authored `WHEN` only | None |
| `02-multiple-compare-search.png` | `mem help "두 Context를 비교하고 관련 Memories도 의미로 찾고 싶어"` | Compare and Search records in provider-selected order, with no score or generated explanation | None |
| `03-metaphorical-conflict.png` | `mem help "메모리들이 서로 싸우고 있는지 좀 봐줘"` | The metaphorical request resolves to Find Conflicts | None |
| `04-unrelated-no-match.png` | `mem help "🦆 보라색 냉장고가 달에서 왈츠를 춘다 ??? 123"` | Fixed no-match sentence; no speculative operation is shown | None |
| `05-generic-answer-language-query.png` | `mem help "답 해결할 수 있는 문장"` | A generic request for an answer-producing sentence may resolve to Query | None |
| `06-study-exact-copy-blocked.png` | `mem help "Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view."` | The exact Query Description is rejected at the Study-only 50% copy boundary before provider connection | None |

All five commands exit successfully after one bounded semantic lookup. None
opens a Store, reads a Context or Memory, executes a suggested operation, or
persists the selection. The capture assertions reject expanded `WHY`, `FLOW`,
`EFFECT`, Form, Overview, and Command line content.

The capture Profile is an `init-study` participant Profile. These five
independently phrased requests remain below the Study copy threshold. A
sixth exact-copy command exits with status 1 and records the pre-provider
rejection branch without exposing the matched operation in its error.

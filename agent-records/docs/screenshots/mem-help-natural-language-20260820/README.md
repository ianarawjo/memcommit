# Natural-language `mem help` live capture log

This ordered set begins with one complete real provider-backed Help turn: its
transient `THINKING` state followed by the final three-candidate ranked result.
It then records five more focused lookup outcomes: a single-action request, a
multi-action request, metaphorical language, an intentionally unrelated
request, and generic answer/problem-solving language. The command uses the
pinned `gpt-5.6-sol` / `none` policy. Every successful lookup requires exactly
three distinct catalog operation names in semantic order. Every visible summary
and `WHEN` line comes back from the frozen authored Help catalog rather than
from provider-written prose.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/mem-help-natural-language-20260820/capture.py`
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
  captures run. Focused lookup output itself uses neutral line-oriented text;
  the transient line animates in place and is erased before stable output.

## Ordered invocations

| Image | Exact command | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `00a-campus-wiki-thinking.png` | `mem help "how can I update those campus wiki from mine?"` | The provider-backed lookup is pending and the in-place `MEM HELP · 1/1 · THINKING` liveness line is visible | None |
| `00b-campus-wiki-result.png` | Same running command; no additional input | The transient line has been erased; Update leads three ordered compact candidates | None |
| `01-ranked-compare.png` | `mem help "두 Context의 차이를 보고 싶어"` | Compare leads three ordered candidates; every row contains only command, authored description, and authored `WHEN` | None |
| `02-ranked-compare-search.png` | `mem help "두 Context를 비교하고 관련 Memories도 의미로 찾고 싶어"` | Compare and Search appear in semantic order inside one fixed three-candidate frame | None |
| `03-ranked-metaphorical-conflict.png` | `mem help "메모리들이 서로 싸우고 있는지 좀 봐줘"` | Find Conflicts leads the three candidates selected from metaphorical language | None |
| `04-ranked-unrelated.png` | `mem help "🦆 보라색 냉장고가 달에서 왈츠를 춘다 ??? 123"` | Even unrelated wording receives three closest exploratory catalog possibilities | None |
| `05-ranked-generic-answer-language-query.png` | `mem help "답 해결할 수 있는 문장"` | Query leads three candidates for generic answer-producing language | None |
| `06-study-exact-copy-blocked.png` | `mem help "Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view."` | The exact Query Description is rejected at the Study-only 50% copy boundary before provider connection | None |

All six provider-backed commands exit successfully after one bounded semantic
lookup each and expose exactly three distinct operation rows. None opens a Store,
reads a Context or Memory, executes a suggested operation, or persists the
selection. The capture assertions reject expanded `WHY`, `FLOW`, `EFFECT`,
Form, Overview, and Command line content.

The capture Profile is an `init-study` participant Profile. These six
independently phrased requests remain below the Study copy threshold. A
seventh exact-copy command exits with status 1 and records the pre-provider
rejection branch without exposing the matched operation in its error.

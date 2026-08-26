# Command-attempt outcome capture log

This ordered capture reproduces immediate checkpointed Chunk plus the concise
`mem log --operations` outcome contract against an isolated real CLI store.
Normal success has no status label. Only a proven no-change completion and an
unsuccessful lifecycle are called out in this path.

## Reproduction frame

- Capture command:
  `python agent-records/docs/screenshots/mem-operation-attempt-outcomes-20260820/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated temporary authoring Profile;
  `outcome-demo`
- PTY: `180` columns × `52` rows, set before every observed command and
  verified by live `stty size`
- Color environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `NO_COLOR` removed
- Isolation: a temporary `mem` entry point redirects both the Profile registry
  and Store before importing the real CLI. No personal Profile, Context, or
  attempt ledger is read or written.
- Renderer: actual color-preserving PTY bytes replayed through `pyte` and drawn
  at the full `1832×1124` Menlo terminal canvas. Raw `.typescript` and plain
  `.txt` evidence are retained beside each PNG.
- Fixture: `mem init outcome-demo`, one two-sentence Memory used for immediate
  Chunk application, and one indivisible Memory used for the no-change result.
- Durable-state check: the no-change command preserves the complete fixture
  `context.json` bytes; immediate Chunk changes them once; the following List,
  parser failure, and Log commands preserve the exact post-Chunk bytes. Only
  the Profile command-attempt ledger changes outside that one Chunk checkpoint.

## Ordered evidence

| Image | Exact command / preceding input | Visible state | Durable Context mutation |
| --- | --- | --- | --- |
| `01-chunk-no-change.png` | `mem chunk SHORT_UID` | One indivisible Memory produces one chunk and reports `no changes made` | None |
| `02-chunk-immediate-apply.png` | `mem chunk MULTI_SENTENCE_UID` | Two visible proposed chunks followed directly by the success receipt; no y/n prompt | One checkpointed split |
| `03-chunk-read-only-verification.png` | `mem list` | Both replacement Memories are visible in the Context | None |
| `04-chunk-parser-failure.png` | `mem chunk --method invalid-method` | Typer rejects the invalid enum before `chunk.cmd()` executes; exit 2 | None |
| `05-operation-log-outcomes.png` | `mem log --operations --limit 20` | Normal successful `init`/`add`/`chunk` rows carry no positive label; exceptional Chunk rows show `NO CHANGE` and `FAILED` | None |

The ordered raw streams are required to contain an ANSI foreground style, and
the final Log stream must exclude the alternate-screen sequence. The
reproduction also asserts that `COMPLETED`, `APPLIED`, and `NOT DISPATCHED`
are absent from the visible Log.

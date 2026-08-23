# Quality Find read-only browser capture log

This ordered set records the one-line issue browser used by
`find-ambiguities`, `find-conflicts`, and the complete-DUN finding projection.
Each header freezes the Source and reports the flagged/total Memory or pair
count. Rows use typed `[CONTEXT ...] [MEMORY ...]` references where needed;
they never join the identities with `@`. Ambiguity folds its readings into a
natural `WHY` rationale, Conflict keeps a scoped `WHY`, and Redundancy omits
its repeated rationale. No image contains a detail mode, answer control,
checked reading, obligation, draft, or Apply action.

## Reproduction frame

- Command: `python docs/screenshots/quality-find-read-only-browser-20260822/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set before launch and printed by each child
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` unset
- Profile/current Context: deterministic typed `study/reporting` fixture; no
  Profile or Store is opened
- Provider: not opened; each child receives a validated typed report
- Mutation: none; each close/handoff receipt verifies zero response state,
  unchanged Source digest, zero Context writes, and zero checkpoints
- Evidence: each PNG has its color-preserving `.typescript` stream and a
  replayed `.txt` terminal canvas

## Ordered interaction

| Image | Preceding input | Visible state | Following input | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-ambiguity-one-line-findings.png` | fresh Ambiguity report | Both source-linked findings are understandable as compact logical lines; item 1 is focused | `Down` | None |
| `02-ambiguity-second-finding-focused.png` | `Down` | Item 2 is focused without opening another layer; both issue rows remain visible | `Enter`, `Esc` | None |
| `03-ambiguity-close-verification.png` | inert `Enter`, then `Esc` | Close receipt and explicit no-answer/no-write verification | process exit | None |
| `04-conflict-one-line-finding.png` | fresh Conflict report | Both exact Sources, scope, rationale, and `Enter open Resolve` are visible on one logical line | `Enter` | None |
| `05-conflict-resolve-handoff-verification.png` | `Enter` | Typed Resolve handoff receipt; Find response and write counts remain zero | process exit | None |
| `06-redundancy-one-line-findings.png` | fresh complete-DUN report | Both typed relation rows appear without repeated `WHY` prose; `Enter open Dedun` remains visible | `Down` | None |
| `07-redundancy-second-finding-focused.png` | `Down` | The second evidence row is focused | `Enter` | None |
| `08-redundancy-dedun-handoff-verification.png` | `Enter` | Typed Dedun handoff receipt; Find itself still has no mutation | process exit | None |
| `09-empty-report.png` | fresh zero-finding Ambiguity report | Stable compact empty result with a close-only footer | `Q` | None |

The handoff captures stop at the receiving-operation boundary. Conflict Resolve
continues in the shared Enter-only compact decision surface recorded under
[`compact-execution-decisions-20260822`](../compact-execution-decisions-20260822/);
Dedun retains its own survivor and Apply evidence. Opening either route is not
a decision stored by Find.

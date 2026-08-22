# Quality Find read-only browser capture log

This ordered set records the compact report browser used by
`find-ambiguities`, `find-conflicts`, and the complete-DUN finding projection.
Questions and possible readings remain evidence: no image contains an answer
control, checked reading, obligation, draft, or Apply action.

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
| `01-ambiguity-compact-list.png` | fresh Ambiguity report | Compact finding list focused at item 1 | `Enter` | None |
| `02-ambiguity-read-only-detail.png` | `Enter` | Source, reason, follow-up question, and possible readings as read-only evidence | `Esc` | None |
| `03-ambiguity-one-level-back.png` | `Esc` | The same list restored; no answer state was created | `Esc` | None |
| `04-ambiguity-close-verification.png` | `Esc` | Close receipt and explicit no-write verification | process exit | None |
| `05-conflict-compact-list.png` | fresh Conflict report | Compact conflict list with explicit Resolve handoff affordance | `Enter` | None |
| `06-conflict-source-linked-detail.png` | `Enter` | Both exact Source Memories, reason, and follow-up question | `R` | None |
| `07-conflict-resolve-handoff-verification.png` | `R` | Typed handoff receipt; response count and write/checkpoint counts remain zero | process exit | None |
| `08-redundancy-compact-list.png` | fresh complete-DUN report | Compact evidence list with explicit Dedun handoff affordance | `Enter` | None |
| `09-redundancy-source-linked-detail.png` | `Enter` | Exact relation members and source-linked reason | `D` | None |
| `10-redundancy-dedun-handoff-verification.png` | `D` | Typed handoff receipt; Find itself still has no mutation | process exit | None |
| `11-empty-report.png` | fresh zero-finding Ambiguity report | Stable compact empty result with a close-only footer | `Q` | None |

The handoff captures stop at the receiving-operation boundary. Resolve and
Dedun retain their own review, freshness, authority, and Apply evidence sets;
opening either route is not a decision stored by Find.

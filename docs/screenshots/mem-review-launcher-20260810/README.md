# `mem review` launcher capture log

These images render the actual color-preserving PTY byte stream produced by
`mem review`; they are not synthetic fixtures. macOS Terminal GUI capture was
unavailable to the agent, so the stream was replayed through a VT screen and
rendered at the full terminal canvas size.

## Reproduction frame

- Command: `mem review`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile: `study-alt-20260810-t3-find-additive`
- Store: `/Users/KimMunyeong/.mem-profiles/stores/c8651b54-005b-471e-aa24-579dff2ee3a1`
- Current Context: `task-3/local/personal-memory`
- Renderer: actual cumulative ANSI stream replayed with `pyte`, then drawn at
  `1832×1120` with DejaVu Sans Mono; the matching `.typescript` and plain
  `.txt` evidence is retained beside each PNG.

## Ordered interaction

| Image | Input since the preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-launcher-initial.png` | Launch `mem review` | Aggregate saved-session launcher, recent-first, first Sever session selected | None |
| `02-launcher-selection-moved.png` | `Down` | Second saved Sever session selected; its `APPLIED · SOURCE UNCHANGED` state and detail are visible | None |
| `03-saved-review-open.png` | `Enter` | The selected session opens in the existing Sever report UI as `READ ONLY · APPLIED · REVIEW` | None |
| `04-review-item-open.png` | `Tab`, `Down`, `Enter` | First Sever decision opens with classification, evidence, proposed treatments, and the read-only To Do boundary | None |

The session was closed with `Escape`, then `q`. Before and after this path,
`mem status` reported the same current Context with 0 direct Memories, 0 Memory
Refs, 0 Query Views, 3 embedded Contexts, and 0 checkpoints. No provider turn,
Apply action, new analysis, Memory change, or checkpoint occurred.

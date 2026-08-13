# `mem embed` current Participant Profile capture log

This ordered record runs the real flagless `mem embed` setup against the
currently selected Study Participant Profile rather than a fabricated demo
store. It reads the actual `task-1/participant` namespace, selects the existing
`task-1/participant/construction-updates/route-changes` target, stages a gap
between its real direct Memories, reviews the resulting exact command, and
cancels before the mutation boundary.

The driver hashes every file in the active Profile store before opening the
TUI and after cancellation. It fails unless the full byte digest is unchanged.
The final capture also runs the real read-only `mem show --context
task-1/participant/construction-updates/route-changes` command so the retained
Memory order can be compared with the staged gap.

## Reproduction frame

- Command: `mem embed`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set and verified before launch
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile: `study-20260813T135528Z-d61e7a16 · Participant`
- Current Context: `task-1/participant`
- Selected Child: initial local `practice`
- Selected Into: `task-1/participant/construction-updates/route-changes`
- Position: two rows above the explicit `LAST` default, between real retained
  direct items
- Durable scope: no Embed execution, checkpoint, current-Context change, or
  Profile-store byte change

The capture command was:

```bash
env -u NO_COLOR TERM=xterm-256color COLORTERM=truecolor \
  python docs/screenshots/mem-embed-placement-participant-20260813/capture.py
```

The driver deliberately sets `MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG=1`: a UI
capture should not alter participant research data merely by recording a
cancelled command attempt.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-participant-entry.png` | Launch `mem embed` | The real local Context tree opens with `task-1/participant` as Into; because its direct order is empty, the one legal line is `FIRST = LAST · DEFAULT` | None |
| `02-participant-target.png` | `Tab`, `Right`, `Down`, `Right`, `Down`×4, `Enter` | The shared target tree selects `task-1/participant/construction-updates/route-changes` and expands its nine retained direct Memories under that same row | None |
| `03-participant-position-default.png` | `Tab` | The selector enters its Position layer and adds one checked `LAST · DEFAULT` line after the real Memory order | None |
| `04-participant-gap-hover.png` | `Up`, `Up` | The single line moves between two real Memories; `LAST` remains staged and the append command remains unchanged | None |
| `05-participant-gap-staged.png` | `Enter` | That one middle line becomes checked and the exact review changes to a full adjacent `--before` UID | None |
| `06-participant-exact-command.png` | `Tab` | `TO DO` displays the canonical Participant-profile Child, target, neighbor UID, and one-target effect; it is explicitly not run | None |
| `07-participant-cancelled-verified.png` | `Escape` | Cancellation receipt, unchanged full-store byte digest, unchanged current Context, and actual `mem show` direct order | None |

The disposable success/apply path remains separately recorded because applying
an artificial Embed to the Study Participant Profile would contaminate the
research state merely to obtain a screenshot.

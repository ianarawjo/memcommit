# `mem embed` current Participant Profile capture log

This ordered record runs the real flagless `mem embed` setup against the
currently selected Study Participant Profile rather than a fabricated demo
store. It starts from the actual `practice/source` current Context, edits the
proposed command to select the existing
`task-1/participant/construction-updates/route-changes` target and a real gap;
those values appear in the upper controls before Enter is pressed. The flow
then cancels before the mutation boundary.

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
- Profile: `study-20260819T175451Z-5ce5d722 · Participant`
- Current Context: `practice/source`
- Selected Child: initial local `practice`
- Selected Into: `task-1/participant/construction-updates/route-changes`
- Position: immediately before the second-to-last real retained direct item
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
| `01-participant-entry.png` | Launch `mem embed` | The real local Context tree opens with current `practice/source` as Into and local `practice` as the initial Child | None |
| `02-participant-editable-command.png` | `Tab`×4 | The small blue `COMMAND · RUNNABLE` box contains only the initial canonical command with a collision-safe short selector | None |
| `03-participant-invalid-command-red.png` | `Ctrl-U`, then type incomplete `mem embed practice --into` | The compact box turns red with one short reason, Enter is blocked, and the real upper checked Target and gap remain unchanged | None |
| `04-participant-live-synced-controls.png` | Continue typing the exact Target and `--before PREFIX`; no Enter | As soon as the command becomes valid against the frozen real catalog, the box returns to blue, the target's direct Memories appear, and its requested gap is checked | None |
| `05-participant-cancelled-verified.png` | `Escape` | Cancellation receipt, unchanged full-store byte digest, unchanged `practice/source` current Context, and actual `mem show` direct order | None |

The disposable success/apply path remains separately recorded because applying
an artificial Embed to the Study Participant Profile would contaminate the
research state merely to obtain a screenshot.

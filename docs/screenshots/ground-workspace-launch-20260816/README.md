# Ground workspace launch TUI evidence

All images are captured from the actual prompt-toolkit screens in a
color-capable `180 × 52` PTY with `TERM=xterm-256color`,
`COLORTERM=truecolor`, and `NO_COLOR` removed. The fixture uses an isolated
Store, one ordinary `projects` Context as Current, a deterministic Ground
dialogue response, and the real physical-workspace application boundary. The
exact approved argv is invoked in-process only so the isolated Store remains
shared by every captured screen.

| # | Snapshot | Command and preceding input | Visible state | Durable effect |
| --- | --- | --- | --- | --- |
| 01 | `01-empty-launcher.png` | `mem ground` | `SAVED GROUNDS OR NEW CONTEXT` opens even without saved Grounds; `CREATE NEW GROUND CONTEXT` is the pinned action. | None |
| 02 | `02-save-location.png` | `Enter` | The shared parent tree and exact `NEW GROUND · SAVE LOCATION` field open with `NOT CREATED`. | None |
| 03 | `03-exact-location-edited.png` | `Ctrl-U`, `projects/ticker-ground` | The person-owned exact physical root is visible before dialogue. | None |
| 04 | `04-unsaved-workspace.png` | `Enter` | Blank Ground opens with a `WORKSPACE` pane showing the fixed root and five future child Contexts; no existing-Context recommendation is present. | None |
| 05 | `05-goal-thinking.png` | Enter the Goal request | The Goal pane retains the request and owns `GOAL · THINKING… · REVISING`; the footer contains no generic Context-ranking spinner. | None |
| 06 | `06-goal-revision-proposed.png` | Wait for the deterministic provider response | The proposed Goal revision remains in Goal, while Chat does not receive a duplicate focused turn. | None |
| 07 | `07-exact-creation-review.png` | `Tab` × 4 | Chat contains only the separate exact `mem ground projects/ticker-ground --goal ...` command review. | None |
| 08 | `08-physical-workspace.png` | `Enter` | After approval, the physical workspace navigator opens on the six saved Contexts. | Root, manifest, Goal, and five child Contexts are created atomically. |
| 09 | `09-durable-verification.png` | `Q` | The command confirms six physical Contexts, no legacy Ground JSON, and unchanged global Current. | None after creation. |

Regenerate with:

```bash
python docs/screenshots/ground-workspace-launch-20260816/capture.py
```

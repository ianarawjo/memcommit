# Ground session draft and in-session Location TUI evidence

All images are captured from the actual prompt-toolkit screens in a
color-capable `180 × 52` PTY with `TERM=xterm-256color`,
`COLORTERM=truecolor`, and `NO_COLOR` removed. The fixture uses an isolated
Store, one ordinary `projects` Context as Current, a deterministic Ground
dialogue response, and the real physical-workspace application boundary. The
exact approved argv is invoked in-process only so the isolated Store remains
shared by every captured screen.

| # | Snapshot | Command and preceding input | Visible state | Durable effect |
| --- | --- | --- | --- | --- |
| 01 | `01-session-launcher.png` | `mem ground` | The one Ground session list opens with `START NEW GROUND SESSION`. | None |
| 02 | `02-blank-session.png` | `Enter` | A blank workbench opens immediately with initial focus on `GOAL`; `LOCATION` is above it and says `NOT SET`. | None |
| 03 | `03-location-picker.png` | `Shift-Tab`, `Enter` | Location is a real focus surface; Enter expands the shared parent tree and exact `NEW GROUND · SAVE LOCATION` field. `L` remains a shortcut. | None |
| 04 | `04-exact-location-edited.png` | `Ctrl-U`, `projects/ticker-ground` | The person-owned exact physical root is visible but remains `NOT CREATED`. | None |
| 05 | `05-location-selected.png` | `Enter` | The workbench resumes with the selected Location above Goal and all six future Context names in the workspace preview. | None |
| 06 | `06-goal-thinking.png` | `Tab`, `Enter`, type the Goal request, `Enter` | Returning from Location preserves that focus; Tab reaches Goal, whose pane owns the provider liveness state. | None |
| 07 | `07-goal-proposed.png` | Wait for the deterministic response | Goal and exact creation command are proposed with the selected Location. | None |
| 08 | `08-draft-in-session-list.png` | `B` | The same launcher now contains `projects/ticker-ground` as `DRAFT · NOT CREATED`. | One private draft receipt; no Context, manifest, or checkpoint. |
| 09 | `09-resumed-exact-review.png` | `Down`, `Enter` | The pending proposal is restored without another provider call and remains ready for exact approval. | None |
| 10 | `10-physical-workspace.png` | `Tab` × 4, `Enter` | From resumed Goal, Tab reaches Chat; exact approval opens the physical workspace navigator on the six saved Contexts. | Root, manifest, Goal, and five child Contexts are created atomically; draft receipt removed. |
| 11 | `11-durable-verification.png` | `Q` | The command confirms one provider call, draft removal, six physical Contexts, no legacy Ground JSON, and unchanged Current. | None after creation. |

Regenerate with:

```bash
python agent-records/docs/screenshots/ground-session-draft-location-20260816/capture.py
```

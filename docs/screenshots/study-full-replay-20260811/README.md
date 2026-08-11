# Full Study replay snapshots

This directory records a fresh participant Study run from `init-study` onward.
Every capture uses the real `mem` executable in a `180 × 52` color-capable PTY.
The run name is `study-snapshot-replay-20260811`; the selected baseline is
`study-baseline`.

## Init Study interaction log

| Capture | Command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-init-study-name-entry` | `mem init-study` | terminal CPR response only | Generated Study name editor | None |
| `02-init-study-name-edited` | same | `Ctrl-U`, then `study-snapshot-replay-20260811` | Exact replacement name | None |
| `03-init-study-success` | same | `Enter` | Participant/authority pair, grants, and all declared prewarm installation counts | New Study pair created and participant Profile selected |
| `04-active-profile-status` | `mem profile current` | None | Active Profile and Task 1 current Context | None; read-only |
| `05-init-study-action-log` | `mem log --actions --limit 20` | None | `STUDY_CREATED`, `PROFILE_ENTERED`, and command boundary events | None; read-only |

Capture environment:

- PTY dimensions are set and verified as `52 180` before every command.
- `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT` are set.
- `NO_COLOR` is removed.
- Each numbered state has a raw `.typescript`, terminal-text `.txt`, and
  full-canvas `.png` artifact.

Later sections in this directory will continue the same run through each
prepared semantic operation. A new capture is added only when visible state or
the durable safety boundary changes.

## Tutorial Atomize interaction log

| Capture | Command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `06-atomize-exact-prewarm-entry` | `mem atomize --context practice/source` | None | Installed one-to-eight exact analysis in the common workbench | None |
| `07-atomize-split-detail` | same | `Tab`, `Down`, `Enter` | Source-linked split rationale and proposed result | None |
| `08-atomize-review-handoff` | same | `Backspace` | Restored report with visible `REVIEW AND APPLY` handoff | None |
| `09-atomize-final-review` | same | `A` | Non-mutating final review summary | None |
| `10-atomize-exact-approval` | same | `End` | Exact `APPLY AS IS` action focused | None |
| `11-atomize-apply-receipt` | same | `Enter` | Eight projected Memories and checkpoint receipt | Created `practice/source-atomized` and switched to it |
| `12-atomize-output-verification` | `mem show --context practice/source-atomized` | None | All eight durable projected Memories | None; read-only |
| `13-atomize-action-log` | `mem log --actions --limit 35` | None | Approval and completed-command boundary events, with no provider event | None; read-only |

The capture harness independently compares the Study ledger's provider-event
count before and after the Atomize command. The count must remain unchanged;
the installed exact analysis is decoded and applied without a live semantic
turn.

## Task 1 Compare interaction log

| Capture | Command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `14-task1-compare-exact-entry` | `mem compare --from task-1/participant/construction-updates --to task-1/campus-wiki --reference-descendants --compared-descendants` | None | Exact 75+300 report with 51 retained relations | None |
| `15-task1-compare-relation-detail` | same | `Tab`, `End`, `Up` × 50, `Enter` | First source-linked retained relation and its judgment | None |
| `16-task1-compare-close-receipt` | same | `Q` | Explicit close receipt | None |
| `17-task1-compare-snapshot-verification` | same with `--snapshot` | None | Stable noninteractive exact report | None; read-only |
| `18-task1-compare-action-log` | `mem log --actions --limit 20` | None | Completed Compare command with no provider event | None; read-only |

`task1-compare-replay-metrics.json` records the measured time from process
start to the first complete report and the unchanged provider-event counter.
The exact analysis remains retained under the run-local current Grant binding.

## Task 1 Update interaction log

| Capture | Command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `19-task1-update-exact-entry` | `mem update --from task-1/participant/construction-updates --to task-1/campus-wiki --source-descendants --target-descendants` | None | Exact 32-edit + 42-add plan | Staged run-local Update receipt only |
| `20-task1-update-edit-detail` | same | `Tab`, `Down`, `Enter` | First edit's before, after, reason, and Source provenance | None |
| `21-task1-update-final-review` | same | `A` | Non-mutating 74-change final review | None |
| `22-task1-update-exact-approval` | same | `End` | Exact Apply action focused | None |
| `23-task1-update-apply-receipt` | same | `Enter` | Applied granted-target report | Target changed from 300 to 342 Memories; Source unchanged |
| `24-task1-update-applied-target` | `mem show --context task-1/campus-wiki/building-access` | None | Construction-qualified durable target text | None; read-only |
| `25-task1-update-undo-receipt` | `mem undo` | None | Command-unit restoration receipt | Restored all affected granted target Contexts |
| `26-task1-update-restored-target` | `mem show --context task-1/campus-wiki/building-access` | None | Original unqualified durable target text | None; read-only |
| `27-task1-update-action-log` | `mem log --actions --limit 25` | None | Approval, Update, and Undo command boundaries | None; read-only |

`task1-update-replay-metrics.json` records the 75-to-300 input, 74
operations, applied 342-Memory target, and exact 300-Memory digest restoration.
Undo is part of this replay's isolation protocol: it lets the later Task 1
Directional Meld exercise its own exact prewarm against the unchanged fixture.

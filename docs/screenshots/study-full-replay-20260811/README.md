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

## Task 1 symmetric Meld interaction log

The result Context was created by
`mem meld task-1/participant/construction-updates task-1/campus-wiki
--left-descendants --right-descendants --to
task-1/participant/symmetric-replay-result`. The captured review reopens that
target-bound session after switching to the result Context, as required by the
ordinary symmetric Meld resume contract.

| Capture | Command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `28-task1-symmetric-meld-target-switch` | `mem switch task-1/participant/symmetric-replay-result` | None | The empty symmetric result becomes current | Current-Context pointer only |
| `29-task1-symmetric-meld-exact-entry` | `mem meld task-1/participant/construction-updates task-1/campus-wiki --left-descendants --right-descendants` | None | Exact 75+300 Compare basis, 51 relations, 24 optional issues, and zero proposed result Memories | None |
| `30-task1-symmetric-meld-relation-detail` | same | `Tab`, `Down`, `Enter` | First scoped relation with exact source claims and two participant response choices | None |
| `31-task1-symmetric-meld-preserve-all` | same with `--preserve-all` | None | Deterministic 375/375 Source and 51/51 relation coverage; exact accept command exposed | Saved ready proposal only |
| `32-task1-symmetric-meld-accept-receipt` | same with `--accept` | None | Green checkpoint receipt for all 375 Meld results | Materialized 375 result Memories |
| `33-task1-symmetric-meld-result-verification` | `mem show --context task-1/participant/symmetric-replay-result` | None | Durable result contents; the raw stream begins with `Memories 375` | None; read-only |
| `34-task1-symmetric-meld-action-log` | `mem log --actions --limit 30` | None | Three completed Meld attempts at 180 by 52 with no provider event | None; read-only |
| `35-task1-symmetric-meld-current-restored` | `mem switch practice/source-atomized` | None | Tutorial output restored as the current Context | Current-Context pointer only |

`task1-symmetric-meld-replay-metrics.json` records a `1.923` second captured
review attempt, `0.097` second deterministic preserve-all step, and `0.128`
second exact acceptance. The provider-event counter remained `0` throughout.
The preservation branch is a lossless mechanics check, not a claim that a
participant-guided semantic synthesis would choose the same 375-Memory result.

## Task 1 directional Meld interaction log

| Capture | Command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `36-task1-directional-meld-exact-entry` | `mem meld task-1/participant/construction-updates --left-descendants --into task-1/campus-wiki --right-descendants` | None | Directional 75-into-300 review with 51 relations, 24 optional issues, 75 changes, and complete Source coverage | Saved exact-prewarm proposal only |
| `37-task1-directional-meld-relation-detail` | same | `Tab`, `Down`, `Enter` | First source-linked relation and its optional consolidation question | None |
| `38-task1-directional-meld-final-review` | same | `Backspace`, `A` | Non-mutating final review with all 24 optional issues left open | None |
| `39-task1-directional-meld-exact-approval` | same | `Down` | Exact Apply card focused; Enter is explicitly bound to apply | None |
| `40-task1-directional-meld-apply-receipt` | same with `--accept` after the interactive Apply | `Enter`, followed by recovery verification | APPLIED report and no-duplicate-checkpoint receipt | The preceding approved turn added 75 owner-routed Memories; recovery changed nothing |
| `41-task1-directional-meld-target-verification` | `mem show --context task-1/campus-wiki/building-access` | None | Standing baseline and new construction-scoped Memories coexist | None; read-only |
| `42-task1-directional-meld-source-verification` | `mem show --context task-1/participant/construction-updates` | None | Original seven-child Source remains present | None; read-only |
| `43-task1-directional-meld-action-log` | `mem log --actions --limit 25` | None | Review presentation, exact acceptance, completed Meld command, and no provider event | None; read-only |

Before opening the captured review, the harness matched the saved session
against the installed Task 1 directional artifact. The approved 180 by 52 PTY
attempt completed in `4.422` seconds. Durable verification found the Source
unchanged at `75` Memories and the granted baseline expanded from `300` to
`375`. The 75 additions were routed across all six authoritative child
Contexts; `task1-directional-meld-replay-metrics.json` records the exact
per-owner counts. The provider-event counter remained `0`.

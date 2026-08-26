# Full Study replay snapshots

This directory records a fresh participant Study run from `init-study` onward.
Every capture uses the real `mem` executable in a `180 × 52` color-capable PTY.
The run name is `study-snapshot-replay-20260811`; the selected baseline is
`study-baseline`.

Observer-authored participant journals narrate every capture in order and
separate the operation, visible outcome, and issue or research note:

- [English participant journal](./PARTICIPANT-JOURNAL.en.md)
- [한국어 참가자 저널](./PARTICIPANT-JOURNAL.ko.md)
- [Editable English Word journal](./PARTICIPANT-JOURNAL.en.docx)
- [수정 가능한 한국어 Word 저널](./PARTICIPANT-JOURNAL.ko.docx)

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

## Task 2 Compare interaction log

| Capture | Command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `44-task2-compare-exact-entry` | `mem compare --from task-2/advisor1 --to task-2/advisor2 --reference-descendants --compared-descendants` | None | Exact 150+150 report with 98 relations and five potential conflicts | None |
| `45-task2-compare-relation-detail` | same | `Tab`, `End`, `Up` times 97, `Enter` | Opening-length conflict with exact claims from both advisors | None |
| `46-task2-compare-close-receipt` | same | `Q` | Explicit close receipt | None |
| `47-task2-compare-snapshot-verification` | same with `--snapshot` | None | Stable retained report and the exact symmetric Meld follow-up command | None; read-only |
| `48-task2-compare-action-log` | `mem log --actions --limit 20` | None | Completed Compare attempts with no provider event | None; read-only |

The full exact report appeared in `0.412` seconds. The retained analysis has
`18` equivalent, `14` compatible, `26` scoped, `5` conflict, and `35`
distinct groups. `task2-compare-replay-metrics.json` records the unchanged
zero provider-event counter.

## Task 2 symmetric Meld interaction log

| Capture | Command | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `49-task2-symmetric-meld-exact-entry` | `mem meld task-2/advisor1 task-2/advisor2 --left-descendants --right-descendants --to task-2/participant/symmetric-replay-result` | None | Exact 150+150 Compare basis, 98 relations, five required conflicts, and empty result | Created the empty result and target-bound review session |
| `50-task2-symmetric-meld-conflict-detail` | same | `Tab`, `Down`, `Enter` | Required opening-length conflict with exact claims and two distinct resolution choices | None |
| `51-task2-symmetric-meld-target-switch` | `mem switch task-2/participant/symmetric-replay-result` | None | Empty result becomes the current Meld target | Current-Context pointer only |
| `52-task2-symmetric-meld-preserve-all` | resumed Meld with `--preserve-all` | None | Deterministic 300/300 Source and 98/98 relation coverage | Saved ready proposal only |
| `53-task2-symmetric-meld-accept-receipt` | resumed Meld with `--accept` | None | Green checkpoint receipt for 249 Meld results | Materialized 249 result Memories |
| `54-task2-symmetric-meld-result-verification` | `mem show --context task-2/participant/symmetric-replay-result` | None | Durable coalesced and preserved advisor contents | None; read-only |
| `55-task2-symmetric-meld-action-log` | `mem log --actions --limit 25` | None | Completed initial, preserve, and accept attempts with no provider event | None; read-only |
| `56-task2-symmetric-meld-current-restored` | `mem switch practice/source-atomized` | None | Prior tutorial result restored as current | Current-Context pointer only |

The initial review appeared in `0.501` seconds, deterministic preservation in
`0.452` seconds, and exact acceptance in `0.475` seconds. Equivalent advisor
claims were coalesced, so 300 inputs produced 249 provenance-bearing result
Memories. Required conflicts remain visible in the participant-guided path;
preserve-all is retained here only as the provider-free coverage control. The
provider-event counter remained `0`.

## Task 3 year-pair Compare interaction log

| Captures | Command pair | Visible states | Durable mutation |
| --- | --- | --- | --- |
| `57` through `60` | `2024` versus `2025`, both descendant-inclusive | Exact 120+120 report, 119 relations, first birthday-timing relation, close receipt, stable snapshot | None |
| `61` through `64` | `2024` versus `2026`, both descendant-inclusive | Exact 120+60 report, 96 relations, first restaurant-noise relation, close receipt, stable snapshot | None |
| `65` through `68` | `2025` versus `2026`, both descendant-inclusive | Exact 120+60 report, 102 relations, first repeated-speech relation, close receipt, stable snapshot | None |
| `69-task3-year-compares-action-log` | `mem log --actions --limit 30` | The three interactive and three snapshot Compare completions with no provider event | None; read-only |

For every pair, the ordered captures are `exact-entry`, `relation-detail`,
`close-receipt`, then `snapshot-verification`. The reports appeared in `0.368`,
`0.371`, and `0.403` seconds respectively. The local-local retained label is
`EXACT PREWARM`; unlike granted comparisons, it does not need a run-local
Grant-binding suffix. `task3-year-compares-replay-metrics.json` records all
three input sizes, relation counts, timings, and the unchanged provider-event
counter of `0`.

## Task 3 year-pair symmetric Meld interaction log

| Captures | Pair | Visible and durable result |
| --- | --- | --- |
| `70` through `75` | `2024 + 2025` | 119-relation review, seven optional issues, complete preservation, exact acceptance, 240-Memory result |
| `76` through `81` | `2024 + 2026` | 96-relation review, ten optional issues, complete preservation, exact acceptance, 180-Memory result |
| `82` through `87` | `2025 + 2026` | 102-relation review, two optional issues, complete preservation, exact acceptance, 174-Memory result after equivalent claims coalesce |
| `88-task3-year-melds-current-restored` | all pairs complete | `practice/source-atomized` restored as current; the three result Contexts remain separate |
| `89-task3-year-melds-action-log` | `mem log --actions --limit 60` | Initial review, preserve, accept, and verification command boundaries with no provider event |

Each six-capture pair follows the same order: `exact-entry`, `issue-detail`,
`target-switch`, `preserve-all`, `accept-receipt`, and
`result-verification`. The initial reviews took `0.400`, `0.388`, and `0.390`
seconds. Preservation took `0.490`, `0.470`, and `0.458` seconds; acceptance
took `0.536`, `0.505`, and `0.506` seconds. All three branches covered every
input and retained the exact relation basis without a provider event.

## Task 3 rule-pair Compare interaction log

| Capture | Command or input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `90-task3-rule-compare-exact-entry` | `mem compare --from task-3/local/guardrails --to task-3/remote/government/healthcare-agent/info-request/transmission-guidance --reference-descendants --compared-descendants` | Exact local-to-granted 75+25 report with 57 relations | None |
| `91-task3-rule-compare-relation-detail` | `Tab`, `End`, `Up` times 56, `Enter` | Scoped relation between general purpose minimization and healthcare-specific review | None |
| `92-task3-rule-compare-close-receipt` | `Q` | Explicit close receipt | None |
| `93-task3-rule-compare-snapshot-verification` | same Compare with `--snapshot` | Stable retained analysis and follow-up symmetric Meld command | None; read-only |
| `94-task3-rule-compare-action-log` | `mem log --actions --limit 20` | Completed Compare commands with no provider event | None; read-only |

The exact mixed-authority report appeared in `0.376` seconds. Its 57 groups
retain `14` compatible, `2` scoped, and `41` distinct relations. The installed
artifact was rebound to the fresh Study Grant before this participant-facing
lookup; `task3-rule-compare-replay-metrics.json` records the zero provider
events.

## Task 3 rule-pair symmetric Meld interaction log

| Capture | Command or input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `95-task3-rule-meld-exact-entry` | exact rule-pair Meld with descendant scopes and `--to task-3/participant/rule-meld-replay-result` | 57-relation mixed-authority review and empty result | Created the empty local result and saved review session |
| `96-task3-rule-meld-issue-detail` | `Tab`, `Down`, `Enter` | First scoped relation, exact claims, and optional resolution choices | None |
| `97-task3-rule-meld-target-switch` | switch to the result | Empty result becomes current | Current-Context pointer only |
| `98-task3-rule-meld-preserve-all` | resumed Meld with `--preserve-all` | Complete 100/100 Source and 57/57 relation coverage | Saved ready proposal only |
| `99-task3-rule-meld-accept-receipt` | resumed Meld with `--accept` | Green 100-result checkpoint receipt | Materialized 100 result Memories |
| `100-task3-rule-meld-result-verification` | `mem show --context task-3/participant/rule-meld-replay-result` | Durable local and granted rule provenance | None; read-only |
| `101-task3-rule-meld-action-log` | `mem log --actions --limit 25` | Completed initial, preserve, and accept attempts with no provider event | None; read-only |
| `102-task3-rule-meld-current-restored` | switch to `practice/source-atomized` | Prior current Context restored | Current-Context pointer only |

The review appeared in `0.407` seconds, preservation in `0.430` seconds, and
acceptance in `0.432` seconds. All 100 inputs remained separately
provenance-bearing in the result. Neither the local guardrails nor the granted
authority frame changed, and the provider-event counter remained `0`.

## Task 3 Sever interaction log

| Capture | Command or input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `103-task3-sever-exact-entry` | `mem sever --source task-3/local/personal-memory --criteria task-3/local/guardrails --save-as task-3/participant/subtractive-first --source-descendants --criteria-descendants` | Whole-frame 300-Source review, 75 descendant-inclusive Criteria Memories, and an uncreated Result | Saved exact-prewarm review session only |
| `104-task3-sever-candidate-detail` | `Tab`, `Down`, `Enter` | First Source Memory, applicable purpose criterion, and selected `FORGET` recommendation | None |
| `105-task3-sever-final-review` | `Escape`, `A` | All 300 required responses answered; final action remains non-mutating | None |
| `106-task3-sever-exact-approval` | `Down` | Exact Apply card focused with an explicit Enter action | None |
| `107-task3-sever-apply-receipt` | `Enter` | `EXACT PREWARM`, provider-not-called receipt and all 300 `FORGET` outcomes; the visible terminal ends at outcome 300 | Created the empty local Result; Source unchanged |
| `108-task3-sever-empty-result-verification` | `mem show --context task-3/participant/subtractive-first` | Durable Result with zero Memories | None; read-only |
| `109-task3-sever-source-verification` | `mem show --context task-3/local/personal-memory` | Source root and its year descendants remain attached; recursive binding verification still counts 300 Memories | None; read-only |
| `110-task3-sever-undo-receipt` | `mem undo` | Command-unit removal receipt for the new zero-Memory Result | Removed the Result Context; Source unchanged |
| `111-task3-sever-redo-receipt` | `mem redo` | Command-unit restoration receipt | Restored the same Result Context identity and application |
| `112-task3-sever-restored-result-verification` | `mem show --context task-3/participant/subtractive-first` | Restored Result remains empty | None; read-only |
| `113-task3-sever-action-log` | `mem log --actions --limit 35` | Exact approval, Sever completion, Undo, and Redo boundaries with no provider event | None; read-only |

`task3-sever-replay-metrics.json` records `0.596` seconds to the complete
review, `5.401` seconds through inspection and explicit Apply, `0.462` seconds
for Undo, and `0.553` seconds for Redo. Every one of the 300 Source Memories
received a `FORGET` disposition. The new Result therefore contains zero
Memories, while the Source stayed at 300 and retained the identical full-frame
digest. The provider-event counter remained `0`.

This replay also exposed two interaction-boundary defects before the final
capture. Closing a Resolution detail could clear its first staged choice when
final review opened, and an old granted-Update receipt could mask a newer local
Redo when the authority-side stack was empty. The focused regression fixes
retain explicit review state and allow only the proven empty-stack fallback;
revocation, authority drift, and exact-unit ordering failures still fail
closed.

## Full replay verification

| Capture | Command | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `114-final-profile-verification` | `mem profile current` | Fresh replay Profile, 73 owned plus 43 granted Contexts, and restored tutorial current Context | None; read-only |
| `115-final-current-context-verification` | `mem status` | Eight atomized tutorial Memories and their two retained checkpoints | None; read-only |
| `116-final-action-log` | `mem log --operations --limit 20` | Newest-first command ledger, including the final completed 300-by-75 Sever and completed Redo | None; read-only |

`full-replay-summary.json` verifies a contiguous `1` through `116` capture set,
all eleven operation metric files, zero semantic provider events, and every
recorded foreground stage below the 30-second target. The maximum was the
participant-visible Sever review-through-Apply path at `5.401` seconds. The
final ledger deliberately retains the earlier failed Redo that exposed the
stale granted-receipt routing defect; the newer completed Redo above it is the
post-fix evidence.

Final recursive Memory counts are: tutorial Atomize `8`; Task 1 incoming `75`,
directional target `375`, and symmetric result `375`; Task 2 result `249`;
Task 3 year results `240`, `180`, and `174`; Task 3 rule result `100`; and Task
3 Sever Source `300`, Criteria `75`, Result `0`. Failed automation sessions are
not participant-visible: 22 pre-approval `REVIEWING` Sever records were moved
intact to `agent-records/outputs/study-replay-debug-quarantine-20260811/`, leaving exactly
one applied Sever session in the Study store.

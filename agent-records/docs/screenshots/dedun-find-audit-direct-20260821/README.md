# Direct Dedun, Find, and Audit receipts

This ordered 180×52 color-PTY set records the direct current-Context defaults:
Dedun applies eligible exact-plus-semantic DUN evidence immediately and stores detailed
checkpoint evidence; each quality Find remains read-only; Audit saves a durable
report and returns its Review receipt without opening a result workbench.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/dedun-find-audit-direct-20260821/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile: a separate isolated temporary Store for each scenario
- Current Contexts: `quality/direct-dedun`, `quality/no-change`,
  `quality/direct-find`, `quality/direct-find-exact`, and `quality/direct-audit`
- PTY: live and verified `180` columns × `52` rows
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Provider: deterministic local stub at the real provider interface; calls are
  delayed so transient progress states can be captured
- Rendering: actual cumulative ANSI PTY streams rendered at full canvas; every
  PNG retains matching `.typescript` and plain `.txt` evidence
- Color verification: raw streams must contain the real green success, yellow
  semantic-result, shared ADD-blue `SURVIVOR`, shared REMOVE-red `ABSORB`, and
  shared lavender/yellow/red `REDUNDANCIES`/`AMBIGUITIES`/`CONFLICTS` foreground
  styles; these line-oriented routes have no focused-control background

## Ordered interaction log

| Capture | Exact command | Input since preceding capture | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-dedun-direct-progress` | `mem dedun` | launch | compact one-line analysis progress; no setup screen | none yet |
| `02-dedun-applied-receipt` | same process | provider returns | one absorbed Memory, checkpoint/Review/recovery receipt | one `dedun` checkpoint |
| `03-dedun-checkpoint-review` | `mem review dedun --receipt UID --snapshot` | `Enter` | immutable APPLIED evidence with blue `SURVIVOR`, red `ABSORB`, and semantic reason | none |
| `03b-dedun-interactive-review` | `mem review dedun --receipt UID` | `Enter` | the same typed blue/red disposition tokens inside the interactive read-only Viewer | none |
| `04-dedun-read-only-verification` | same process | `Q`, then `Enter` | two surviving Memories and exactly one Dedun checkpoint | none |
| `05-dedun-no-change-progress` | `mem dedun` | launch in no-change Context | compact one-line analysis progress | none |
| `06-dedun-no-change-receipt` | same process | provider returns | no redundancies; three Memories and zero checkpoints | none |
| `07-find-direct-progress` | `mem find-redundancies` | launch | compact current-Context analysis progress; no setup | none |
| `08-find-read-only-report` | same process | provider returns | three checked Memories, one proposed connected cleanup group, and one proposed absorption with blue `SURVIVOR`, red `ABSORB`, and typed evidence; zero checkpoints | none |
| `08b-find-duplicates-exact-report` | `mem find-duplicates` | launch | three checked direct items, one provider-free exact-DUP group, and one proposed absorption with two self-contained colored member rows; zero checkpoints | none |
| `09-audit-duplicates-progress` | `mem audit` | launch | compact `1/3` Redundancy stage | none |
| `10-audit-ambiguities-progress` | same process | provider returns | compact `2/3` Ambiguity stage | none |
| `11-audit-conflicts-progress` | same process | provider returns | compact `3/3` Conflict stage | none |
| `12-audit-saved-receipt` | same process | provider returns | saved Source scope and truthful per-check units: Redundancy groups/absorptions, Ambiguity flagged/direct Memories, and Conflict involved/direct Memories plus flagged/checked pairs; up to three source-linked previews plus `… N more`, session UID, and exact Review command | saved Audit artifact only |
| `13-audit-saved-review` | `mem review audit --session UID --snapshot` | `Enter` | exact durable three-check report with compact `SOURCE` and direct-Memory `SNAPSHOT` rows | none |
| `14-audit-read-only-verification` | same process | `Enter` | unchanged Source and zero Context checkpoints | none |

The explicit `--select` setup branches remain available for the read-only
finders and Audit; their established setup mechanics are recorded separately.

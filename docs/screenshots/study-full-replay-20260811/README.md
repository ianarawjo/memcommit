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

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

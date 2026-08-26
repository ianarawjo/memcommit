# Study CPR-safe input verification

These captures verify the Study action recorder fix with the real `mem`
executable in a color-capable `180×52` PTY. The capture script removes
`NO_COLOR`, sets `TERM=xterm-256color` and `COLORTERM=truecolor`, answers the
terminal's CPR request as `ESC [ 1 ; 1 R`, and asserts that the raw stream
contains ANSI styling. It rejects the original exception and the secondary CPR
warning.

All durable changes occur under a generated temporary `HOME`, which is removed
after capture. The script builds a Study baseline, creates an authoring Context,
imports the baseline, and creates `cpr-seed-study` only as setup. Host Profile
and Context state are never read or changed.

## Ordered interaction log

| Capture | Exact command | Profile / current Context | Preceding input | Visible state | Durable mutation |
|---|---|---|---|---|---|
| `01-init-study-name-entry` | `mem init-study` | `cpr-seed-study` / `task-1/participant/construction-updates` | terminal CPR response | generated Study name editor | none |
| `02-init-study-name-edited` | same | same | `Ctrl-U`, `cpr-verified-study` | exact replacement name | none |
| `03-init-study-success` | same | switches to `cpr-verified-study` / `task-1/participant/construction-updates` | `Enter` | successful Study run receipt | participant/authority pair and Grants created; active Profile switched |
| `04-init-name-entry` | `mem init` | `cpr-verified-study` / `task-1/participant/construction-updates` | terminal CPR response | generated Context name editor | none |
| `05-init-name-edited` | same | same | `Ctrl-U`, `cpr-init-context` | exact replacement Context name | none |
| `06-init-success` | same | `cpr-verified-study` / `cpr-init-context` | `Enter` | successful Context receipt | Context created and selected |
| `07-profile-picker` | `mem profile` | `cpr-verified-study` / `cpr-init-context` | none | interactive Profile picker | none |
| `08-profile-cancelled` | same | same | `Escape` | cancellation receipt | none |
| `09-profile-list-verification` | `mem profile list` | same | none | active Study pair and `current=cpr-init-context` | none; read-only |
| `10-study-action-log-verification` | `mem log --actions --limit 100` | same | none | completed Study actions, with no CPR key payload | none; read-only |

The capture script is
[`capture_study_cpr.py`](./capture_study_cpr.py). Each numbered step has a raw
`.typescript`, terminal-text `.txt`, and full-canvas `.png` artifact.

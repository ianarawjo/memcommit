# Switch application-boundary interaction log

This ordered color-PTY record verifies the extracted Switch application path
and the deliberately narrower reuse of its neutral Context picker in blank
Ground. It uses a disposable HOME and two ordinary local Contexts, `alpha` and
`beta`; no host Profile or Context is opened.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set and verified before every launch
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Store: disposable HOME created by the capture driver
- Initial current Context: `beta`
- Switch target in the successful branch: `alpha`
- Ground provider: deterministic injected interpretation used only to expose
  the production blank-Ground TUI; no network/provider process

The capture command is:

```bash
env -u NO_COLOR TERM=xterm-256color COLORTERM=truecolor \
  python agent-records/docs/screenshots/switch-application-boundary-20260816/capture.py
```

## Ordered interaction

| Image | Command/path and input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-switch-entry.png` | Launch `mem switch` | Shared picker opens on current `beta` | None |
| `02-switch-direct-preview.png` | `m` | `beta` direct Memory appears as a lavender read-only row | None |
| `03-switch-cancelled.png` | `Escape` | Cancellation plus complete-store and `mem pwd` verification | None |
| `04-switch-target-selected.png` | Relaunch; `Up` | `alpha` is the visible pending Switch target | None |
| `05-switch-applied-and-verified.png` | `Enter` | Typed success receipt and `mem pwd` both report `alpha`; Context bytes are unchanged | Current pointer only |
| `06-ground-name-only-suggestions.png` | Production `run_ground_shell` with deterministic interpretation | MAIN/ALTERNATIVE remain `NAME-ONLY CHECK · NOT BOUND`; `DIRECT SELECT · P` is visible | None |
| `07-ground-direct-picker.png` | `P` | Ground temporarily opens the same neutral Context picker | None |
| `08-ground-not-bound-selection.png` | `Up`, `Enter` | Returned `alpha` is a process-local selected hint and remains `NOT BOUND` | None |
| `09-ground-closed-and-verified.png` | `Escape` | Ground closes; selected hint is reported for test evidence and the complete Store digest/current pointer are unchanged | None |

The driver hashes the complete disposable Store for cancellation and Ground,
and hashes every Context byte for successful Switch. It fails unless Ground
and cancellation are byte-identical, successful Switch changes only the
current pointer, and the actual color stream contains the expected ANSI
foreground styles.

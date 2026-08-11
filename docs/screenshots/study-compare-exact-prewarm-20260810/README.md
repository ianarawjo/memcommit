# Study Compare exact-prewarm TTY capture

These ordered snapshots record the first production Study prewarm slice in a
real `180 × 52` color PTY. The active Profile was
`study-prewarm-proof-20260810`; its current Context was
`task-1/participant/construction-updates`. The command did not mutate Context
content.

| File | Command and preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-exact-prewarm-report.png` | `mem compare --from task-2/advisor1 --to task-2/advisor2 --reference-descendants --compared-descendants` | Saved 150+150 report opened in Viewer with `EXACT PREWARM` origin | None; the analysis was installed during earlier `init-study` setup |
| `02-close-receipt.png` | `q` | Compare workbench closed and verification gate displayed | None |
| `03-read-only-verification.png` | `v`, then the same command with `--snapshot` | Stable noninteractive report plus explicit provider-call, origin, input-count, and PTY checks | None |

Capture environment:

- `TERM=xterm-256color`
- `COLORTERM=truecolor`
- `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`
- `NO_COLOR` removed
- raw PTY stream verified to contain true-color ANSI styles

The capture uses the real stored Task 2 semantic analysis and current run-local
Grant bindings. It does not synthesize the report or invoke a semantic
provider.

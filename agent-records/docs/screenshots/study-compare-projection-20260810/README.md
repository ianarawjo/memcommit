# Study Compare projected-preview TTY capture

These ordered snapshots record the enabled Task 2 descendant projection in a
real `180 × 52` color PTY. The active Profile was
`study-prewarm-proof-20260810`; its current Context was
`task-1/participant/construction-updates`. The command did not mutate Context
content or publish a durable Compare analysis.

| File | Command and preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-projected-report.png` | `mem compare --from task-2/advisor1/style --to task-2/advisor2/style` | 13+13 report opened in Viewer with `PROJECTED · NOT SAVED · PREVIEW`; the footer omits Meld | None |
| `02-close-receipt.png` | `q` | Compare workbench closed and verification gate displayed | None |
| `03-read-only-verification.png` | `v`, then the same command with `--snapshot` | Stable noninteractive report plus explicit zero-provider, projected-origin, input-count, and PTY checks | None |

Capture environment:

- `TERM=xterm-256color`
- `COLORTERM=truecolor`
- `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`
- `NO_COLOR` removed
- raw PTY stream verified to contain true-color ANSI styles

The projection uses the declared exact 150+150 Task 2 parent ledger. It keeps
all 26 requested Memories in exactly one primary relation group, performs no
fresh semantic provider turn, is explicitly approximate, and cannot seed
Meld. Additions, edits, same-parent-side pairs, cross-task pairs, and
`--refresh` use the ordinary live path.

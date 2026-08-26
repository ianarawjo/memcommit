# Tutorial Atomize exact-prewarm TTY capture

These ordered snapshots record the fixed tutorial Atomize prewarm in a real
`180 × 52` color PTY. The active Profile was
`atomize-prewarm-proof-20260810`; its current Context was
`task-1/participant/construction-updates`. The command did not mutate Context
content or create the planned Output.

| File | Command and preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-exact-prewarm-workbench.png` | `mem atomize --context practice/source` | The exact eight-child tutorial analysis opened in the standard Viewer and review flow | None; setup had already installed the analysis and blank workbench |
| `02-close-receipt.png` | `Escape` | Workbench closed with `EXACT PREWARM · CURRENT`, zero-provider resume text, and the not-created Output plan | None |
| `03-read-only-verification.png` | `v` | Stored origin receipt, analysis UID, Source/projected counts, Output name, provider-call count, and PTY size | None |

Capture environment:

- `TERM=xterm-256color`
- `COLORTERM=truecolor`
- `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`
- `NO_COLOR` removed
- raw PTY stream verified to contain true-color ANSI styles

The capture uses the real stored analysis `496dd810-d3b2-4e42-9d90-ff15e0179f99`.
The cold run took 23.29 seconds wall-clock. The identical prewarmed CLI reopen
took 0.36 seconds including Python startup; ten direct production reopens had
a 0.140 ms median and made zero provider calls.

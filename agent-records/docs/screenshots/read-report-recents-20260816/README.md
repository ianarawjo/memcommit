# Read Report Recents TUI evidence

All images were captured from the actual prompt-toolkit UI in a color-capable
PTY with `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed, and
the size explicitly verified as `180 × 52`. The fixture uses an isolated
temporary Profile Store. It invokes the same Typer entry point as
`mem summarize` and `mem find-duplicates`; the finder provider result alone is
replaced with a deterministic empty finding report so this evidence tests the
launcher, source freeze, report workbench, and close lifecycle without an
external provider dependency.

The fixture creates one completed content-free attempt before each command.
Neither attempt contains Memory/report prose, provider output, cache identity,
argv, or callbacks. Every final verification compares the exact Context bytes
and checkpoint UID sequence with their pre-command values.

| # | Snapshot | Command and preceding input | Visible state | Durable effect |
| --- | --- | --- | --- | --- |
| 01 | `01-summarize-recent-entry.png` | `mem summarize` | Summarize Recents shows one `reports/empty` identity with `DIRECT + RECURSIVE`; the detail states that report and Memory content were not retained. | None |
| 02 | `02-summarize-target-revalidated.png` | `Enter` | The selected attempt has been reloaded, the readable target is reauthorized, and the existing Summarize workbench opens with `BOTH` staged. | None |
| 03 | `03-summarize-both-results.png` | `S` | Direct and recursive empty-source results are independently executed and rendered in the operation-owned Summary document. | None |
| 04 | `04-summarize-read-only-verification.png` | `Q` | The TUI has closed; Context bytes and checkpoints match the pre-command snapshot. | None |
| 05 | `05-find-recent-entry.png` | `mem find-duplicates` | Find Recents shows the operation-specific direct target without a saved analysis session. | None |
| 06 | `06-find-report.png` | `Enter` | The recent is reloaded, its exact source is frozen, and the existing process-local quality report opens. | None |
| 07 | `07-find-read-only-verification.png` | `Q` | The TUI has closed; Context bytes and checkpoints match the pre-command snapshot. | None |

The raw ANSI streams (`.typescript`) and plain terminal projections (`.txt`)
are retained beside each PNG. Regenerate with:

```bash
python agent-records/docs/screenshots/read-report-recents-20260816/capture.py
```

# Fit shared Viewer and Ground background turn

This ordered set records the rebuilt Fit interface boundary in a real
`180 × 52` color-capable PTY. It uses isolated temporary Stores and a delayed,
deterministic provider. `TERM=xterm-256color`, `COLORTERM=truecolor`, and
24-bit prompt-toolkit color are enabled; `NO_COLOR` is removed. PNGs are
rendered from the actual ANSI streams, which are retained beside plain canvas
extracts.

Command:

```bash
python docs/screenshots/mem-fit-shared-viewer-20260815/capture.py
```

| # | File | Exact command / preceding keys | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| 01 | `01-standalone-fit-running` | `mem fit ticker-fit --tui` | CLI provider progress before the Viewer exists | none yet |
| 02 | `02-current-viewer-entry` | provider completion | typed shared Viewer at `FIT:TITLE`; current immutable receipt | one Fit receipt only |
| 03 | `03-example-focused` | `Down` ×3 | first Example is the focused semantic section | none |
| 04 | `04-focused-copy` | `y` | only the focused Example projection copied through an injected process-local writer | none |
| 05 | `05-whole-report-copy` | `Y` | complete typed Fit report copied; focus remains on the Example | none |
| 06 | `06-stale-receipt-reopen` | `mem fit ticker-fit --receipt <uid> --tui`, then `PgUp` | immutable prior receipt reports `STALE` after a separately saved Rule revision | no write while reopening |
| 07 | `07-ground-cases-entry` | named Ground entry, then `Tab` ×4 | Ground Memories/Cases before Fit | none |
| 08 | `08-ground-fit-running` | `F` | shared background turn is active; Ground and Contexts remain unchanged | none yet |
| 09 | `09-duplicate-run-close-deferred` | `F`, then `Q` | duplicate run rejected and close visibly waits for the receipt boundary | none yet |
| 10 | `10-ground-fit-verification` | provider completion | one call, one receipt, current freshness, unchanged Ground content, deferred close completed | one Fit receipt only |

The clipboard writer is injected by the capture and does not replace the
user's operating-system clipboard. The standalone and embedded paths both use
the same Fit runtime. Their presentations intentionally differ: standalone Fit
is a read-only semantic Viewer, while Ground projects the latest receipt into
its operation-owned Cases cards.

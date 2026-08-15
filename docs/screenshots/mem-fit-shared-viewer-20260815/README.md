# Compact Fit Viewer and Ground status marks

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
| 02 | `02-current-viewer-entry` | provider completion | compact Viewer at `FIT:SUMMARY`; `✓` marks the current all-fitting receipt | one Fit receipt only |
| 03 | `03-example-focused` | `Down` | the fitting Example is the focused semantic section | none |
| 04 | `04-focused-copy` | `y` | only the focused Example projection copied through an injected process-local writer | none |
| 05 | `05-whole-result-copy` | `Y` | complete compact Viewer projection copied; focus remains on the Example | none |
| 06 | `06-current-issue-focused` | `mem fit ticker-fit --tui`, then `Down` | `!` plus the issue classification and one reason; no overview or receipt chrome | one Fit receipt only |
| 07 | `07-stale-receipt-reopen` | `mem fit ticker-fit --receipt <uid> --tui` | `◷` replaces prior pass/fail marks after a separately saved Rule revision | no write while reopening |
| 08 | `08-ground-cases-entry` | named Ground entry, then `Tab` ×4 | `·` marks the Ground Memory before any Fit receipt | none |
| 09 | `09-ground-fit-running` | `F` | shared background turn is active; Ground and Contexts remain unchanged | none yet |
| 10 | `10-ground-fit-current` | provider completion | `✓` appears on the same Ground Memory row; no result screen or Fit detail block opens | one Fit receipt only |
| 11 | `11-ground-fit-verification` | `Q` | one call, one receipt, current freshness, unchanged Ground content | none |
| 12 | `12-duplicate-run-close-deferred` | separate Ground run: `F`, then `F`, then `Q` | duplicate run is rejected and close visibly waits for the receipt boundary | none yet |
| 13 | `13-deferred-close-verification` | provider completion | deferred close completed after one call and one receipt | one Fit receipt only |

The clipboard writer is injected by the capture and does not replace the
user's operating-system clipboard. The standalone and embedded paths both use
the same Fit runtime and immutable receipt boundary. Fit creates no workbench
session. Their presentations intentionally differ: standalone interactive Fit
is a compact read-only Viewer, non-interactive Fit is one stable summary line,
and Ground projects only `·`, `✓`, `!`, or `◷` onto its existing Memory rows.

# Command-wait QUERY Grant browser capture log

These images render the actual color-preserving PTY byte stream from the shared
interactive command-wait application. A deterministic read-only fixture keeps
the worker alive while the `C` Context browser is inspected. No Profile,
Context, current pointer, provider, or durable receipt is opened or changed.

## Reproduction frame

- Command: `python docs/screenshots/mem-command-wait-query-grants-20260810/capture_query_grants.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified inside the child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Catalog: one ordinary local Context, one READ Grant, and one QUERY Grant
- Worker: deterministic 4.5-second read-only turn; no provider connection
- Renderer: cumulative ANSI replay through `pyte`, then a native-size PNG with
  DejaVu Sans Mono; matching `.typescript` and `.txt` evidence is retained
- Durable mutation: none

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-report-building.png` | Launch | Default report-shaped wait at `ANALYZING` | None |
| `02-query-grant-visible.png` | `c`, `Down` | QUERY Grant public row focused with exact permissions and `UNAVAILABLE` | None |
| `03-report-restored.png` | `m`, `Enter`, `Right`, `M`, `c` | Repeating `c` returns to the originating report after every Memory-expansion path was exercised | None |
| `04-read-only-verification.png` | Worker completes | Loader receipt shows only the ordinary and READ-granted names; `QUERY LOADER CALLED · NO` | None |

The third step deliberately sends the leaf and all-Memory expansion keys while
the opaque QUERY row is focused. The final receipt verifies that the public row
remained orientation-only and never entered the ordinary Context Memory loader.

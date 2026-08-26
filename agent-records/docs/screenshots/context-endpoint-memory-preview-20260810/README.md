# Context endpoint Memory-preview capture log

This ordered set records the new read-only `m`/`M` Memory previews in both the
role-based common endpoint shell and Sever's peer setup shell. Synthetic
Contexts keep the capture entirely process-local: there is no MemoryStore,
Profile, provider connection, receipt, or durable mutation.

## Reproduction frame

- Commands: `python capture.py --child common` and
  `python capture.py --child sever`, orchestrated by `python capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: not consulted; synthetic names are `alpha` and
  `beta`
- PTY: `180` columns × `52` rows; each child prints the live dimensions before
  entering its full-screen application
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the capture helper requires both ANSI foreground and
  background sequences before it succeeds.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-common-entry.png` | Launch common Update-shaped endpoint shell | Source and target Context trees; no Memory content loaded | None |
| `02-common-memory-here.png` | `m` | Alpha's two direct Memory previews appear only below the focused Source tree | None |
| `03-common-memory-focus.png` | `Down` | The first Alpha Memory owns the viewport focus while the retained Context endpoint stays checked | None |
| `04-common-memories-all.png` | `M` | Every visible readable Context Memory is shown; the Memory remains a read-only focus stop | None |
| `05-common-cancel-receipt.png` | `q` | Explicit no-receipt/no-store/no-provider cancellation | None |
| `06-sever-entry.png` | Launch Sever setup | Source, Criteria, and fresh Output draft; no Memory content loaded | None |
| `07-sever-memory-here.png` | `m` | Alpha's Memories appear only below Source | None |
| `08-sever-memory-focus.png` | `Down` | The first Alpha Memory owns viewport focus without selecting a different Source | None |
| `09-sever-memories-all.png` | `M` | All visible readable Memory previews appear in Source | None |
| `10-sever-cancel-receipt.png` | `q` | Explicit no-receipt/no-store/no-provider cancellation | None |

`Enter`/`Space` non-leakage is covered separately by automated tests: a
focused Memory cannot select its parent Context or replace a staged new
endpoint. The captures preserve the corresponding visible focus and retained
check state.

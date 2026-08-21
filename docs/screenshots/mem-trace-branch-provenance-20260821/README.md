# Recorded Branch provenance in Trace

This ordered capture demonstrates the exact boundary fixed for Branch-inherited
Memories. A real `mem checkout -b practice/2` records a Branch receipt, and
Trace projects that receipt as one typed, unchanged Context transition instead
of claiming that Branch creation was missing. A receipt-free legacy copy remains
explicitly uncertain and receives one owner-level warning.

## Reproduction frame

- Command: `python docs/screenshots/mem-trace-branch-provenance-20260821/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Fixture: isolated temporary store; no Profile data is opened or changed
- PTY: `180` columns × `52` rows; the child verifies both
  `os.get_terminal_size()` and `stty size`
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` unset;
  the capture rejects raw streams without foreground and focused-background ANSI
  styles
- Provider boundary: Trace is recorded-data-only and never connects a provider
- Persistence boundary: the setup Branch mutates only the temporary fixture;
  both Trace paths must preserve a complete store digest

## Ordered interaction

| Image | Input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-checkout-branch-receipt.png` | Setup runs `mem checkout -b practice/2` | Actual success output plus the retained Branch checkpoint, stable Memory UID, and `practice/1 → practice/2` route | New `practice/2` in the temporary fixture |
| `02-recorded-branch-trace.png` | `T`, `Enter` | Trace Viewer shows `[branch]`, Source/Target Contexts, and an unchanged `=` Memory row; no missing-Branch warning | None |
| `03-read-only-verification.png` | `q` | Viewer closes and the complete temporary-store digest is unchanged | None |
| `04-legacy-receipt-limit.png` | `L`, `Enter` | A receipt-free copied history emits exactly one owner-level warning and no fabricated Branch event | None |

The legacy fixture deliberately copies the Source checkpoints and Memory UID
without writing a Branch checkpoint. Equal content and a copied Context header
are therefore not treated as authoritative creation evidence.

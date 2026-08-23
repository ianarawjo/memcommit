# Positional Context grammar captures

This ordered set records the positional-first grammar for Merge, Compare, and
Sever introduced or completed on 2026-08-21 and refreshed on 2026-08-23 after
explicit directional aliases were made consistent. Every child ran in a real
color-capable PTY whose live size was 180 columns × 52 rows. `NO_COLOR` was
removed; `TERM=xterm-256color`, `COLORTERM=truecolor`, and prompt-toolkit
24-bit color were enabled. The retained `.typescript` streams contain both
foreground and background ANSI, and each PNG is a full-size `pyte`/Pillow
render of the actual stream.

All execution paths used an isolated temporary MemoryStore and deterministic
local providers. They did not read or change the user's Profile. Run
`python docs/screenshots/context-positional-grammar-20260821/capture.py` from
the repository root to reproduce the complete set.

## Ordered interaction log

| Image | Exact command / preceding input | Visible state | Durable mutation in isolated Store |
| --- | --- | --- | --- |
| `01-merge-help.png` | `mem merge -h` | Usage exposes `[source] [target]`; `--from` selects Source and `--into`/`--to` select Target | None |
| `02-compare-help.png` | `mem compare -h` | One positional Context means PEER; two mean REFERENCE PEER | None |
| `03-sever-help.png` | `mem sever -h` | Usage exposes `SOURCE CRITERIA [RESULT]`; `--source`/`--from`, `--criteria`/`--against`, and `--save-as`/`--to` expose the same roles | None |
| `04-merge-positional-conflict.png` | `mem merge`, then `Tab` ×3, `Enter` in setup | Complete selected Source/Target conflict entry; setup itself publishes nothing | None |
| `05-merge-positional-exact-review.png` | `Tab`, `Enter` | Whole-set KEEP TARGET review shows the portable positional command | None |
| `06-merge-positional-success.png` | `Enter` | One successful Merge receipt and checkpoint | Target changed; Source/current unchanged |
| `07-merge-read-only-verification.png` | `Enter` to close receipt | Current name, Target count, and checkpoint count verified without another action | None after step 6 |
| `08-compare-positional-report.png` | `mem compare capture/compare/reference capture/compare/peer --snapshot` | Equal-authority Compare summary from two explicit positional endpoints | None; snapshot output is process-local and no Context changes |
| `09-compare-close-verification.png` | `Enter` after report pause | Unchanged current Context and `SAVED 0` verification | None |
| `10-sever-default-self-save-receipt.png` | `mem sever capture/sever/source capture/sever/criteria` | Decision-free local TTY path auto-applies the reviewed Result into Source | Source updated under one Sever checkpoint |
| `11-sever-self-save-verification.png` | `Enter` after receipt pause | Source and retained Memory UIDs are preserved, content changed, no other Result exists, current Context is unchanged, provider called once | None after step 10 |
| `12-sever-other-save-receipt-verification.png` | `mem sever capture/sever/source capture/sever/criteria capture/sever/result --accept` | Explicit other-save creates a fresh Result while Source bytes and UID remain unchanged | New Result created; Source has no checkpoint |

The two Sever branches are save-location modes, not relation modes. Self-save
replaces one exact local Source root while preserving its Context and retained
Memory identities. Other-save preserves Source and publishes a require-new
Result. Recursive or granted-Source self-save remains rejected before provider
connection until an owner-aware mutation receipt exists.

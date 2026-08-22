# Compact execution-decision TTY capture

This ordered set records the report-free execution surface shared by Meld,
Update, Forget, and Sever. The deterministic harness uses the real shared
Prompt Toolkit surface and exact-command review component. It retains a full
report route but does not render that report during execution.

## Reproduction frame

- Command: `python docs/screenshots/compact-execution-decisions-20260822/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Scenario: two required Meld conflicts, with three operation-authored choices
  per conflict
- PTY: `180` columns × `52` rows, verified inside each child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`,
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  on a full-size Menlo canvas. Raw `.typescript` and plain `.txt` evidence sit
  beside each PNG; capture fails when true-color ANSI is absent.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-first-conflict.png` | Launch | `MELD NEEDS INPUT · < 1/2 >`; first option focused; complete report hidden | None |
| `02-right-second-conflict.png` | `Right` | Issue 2/2 opens directly; no submission or forced order | None |
| `03-down-second-choice.png` | `Down` | Choice B is the keyboard target; blue focus makes arrow movement visible | None |
| `04-enter-stages-second-choice.png` | `Enter` | Choice B retains `✓`; the process remains on issue 2 | None |
| `05-left-returns-first-conflict.png` | `Left` | Issue 1/2 returns without losing issue 2's staged value | None |
| `06-number-stages-preserve-both.png` | `3` | `Preserve both` is staged directly by number | None |
| `07-one-continue-exact-review.png` | `A` | One exact command review covers both staged judgments | None |
| `08-applied-receipt.png` | `Enter` | Compact applied receipt exposes report Review route | Target checkpoint (fixture receipt) |
| `09-read-only-verification.png` | `v` | Both reviewed choices, retained report, zero unresolved requirements, and no extra provider call | None |
| `10-defer-exact-review.png` | New run, then `D` | Exact non-applying Defer command and effects | None |
| `11-deferred-receipt.png` | `Enter` | Saved report retained; Source and target unchanged; no checkpoint | None |

The two runs demonstrate that arrows alone are sufficient to navigate and
stage a choice, number keys are accelerators rather than a separate mode, and
`D` is a first-class non-applying exit. `(Recommended)` appears only because
the operation fixture explicitly marks that option as recommended.

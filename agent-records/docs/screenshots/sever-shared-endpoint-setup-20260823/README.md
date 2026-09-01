# Sever in-place Endpoint Setup PTY trace

This ordered trace records the current Result-free Sever contract through the
actual `mem sever` CLI callback: Source and Criteria have independent descendant
controls, no Result or Save Location is selectable, and Apply updates each
selected Source owner at its existing Context location.

- PTY: `180` columns × `52` rows, set by `pexpect` and reported by the child.
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, with `NO_COLOR` removed. The raw
  stream is checked for true-color ANSI foreground/background styles.
  `PROMPT_TOOLKIT_NO_CPR=1` suppresses only the cursor-position probe that
  pexpect does not answer.
- Profile: isolated explicit Store; host Grants are excluded.
- Current Context: `capture/reference`.
- Command: `mem sever`.
- Provider: deterministic capture provider; one whole-frame turn receives two
  Source Memories and two Criteria Memories.

| Image | Preceding keys/text | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry.png` | none | Two-role `SOURCE × CRITERIA · IN PLACE` setup; both descendant controls initially enabled; proposed command has no Result operand | none |
| `02-source-root-only.png` | `Tab`, `Tab`, `Space` | Source descendants disabled independently while Criteria descendants remain enabled | none |
| `03-source-memory-preview.png` | `Tab`, `Enter` | Exact Source direct Memory loaded lazily as read-only evidence | none |
| `04-source-descendants.png` | `Escape`, `Shift-Tab`, `Space` | Source descendants re-enabled; exact proposed command includes both descendant flags | none |
| `05-criteria-browse.png` | `Down`, `Tab`, `Enter` | Criteria Browse shows the frozen readable hierarchy, including its descendant and the Source subtree | none |
| `06-two-role-start-review.png` | `Escape`, `Shift-Tab`, `Ctrl-U`, `capture/criteria`, `Tab` × 4 | Focused exact START command is `mem sever capture/reference capture/criteria --source-descendants --criteria-descendants`; no Result | none |
| `07-in-place-success-receipt.png` | `Enter` | Compact success receipt reports two Contexts updated in place and one Undo recovery path | Source root and descendant updated under one Sever command unit |
| `08-owner-verification.png` | `v`, `Enter` | Root and descendant names/UIDs are unchanged; each has one Sever checkpoint; the child Memory was forgotten; no Result Context exists | none after step 7 |
| `09-cancelled-no-mutation.png` | `c`, `Enter`, then `Escape` at the second setup root | Cancellation receipt plus unchanged Store digest | none |

The verification screen also records one provider call, complete `2 × 2`
whole-frame exposure, and two owner checkpoint receipts. The cancellation branch
starts after the successful path and proves that a fresh setup Escape creates no
additional session or checkpoint.

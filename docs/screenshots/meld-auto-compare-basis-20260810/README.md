# Symmetric Meld automatic Compare-basis capture log

This ordered set records the new direct path in which a symmetric Meld starts
without a pre-existing Compare analysis while an unrelated Task 3 Context is
current. The command prepares and saves the exact ordered basis internally; it
does not switch the current Context.

## Reproduction frame

- Command: `mem meld task-2/advisor1 task-2/advisor2 --left-descendants --to task-2/participant/proposal-workspace2`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Host Profile at capture: `study-alt-20260810-t3-find-additive`
- Fixture current Context: `task-3/local/personal-memory`
- Fixture sources: `task-2/advisor1`, `task-2/advisor2`
- Fixture result: `task-2/participant/proposal-workspace2`
- Store: temporary isolated local store; the host Profile store was read only
- Provider: delayed deterministic Compare provider; no network call
- PTY: `180` columns × `52` rows
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: each cumulative raw PTY stream is replayed with `pyte==0.8.2`
  and drawn at the full `1832×1124` canvas with Menlo. Matching
  `.typescript` and plain `.txt` evidence is retained beside every PNG.

The streams contain true-color foreground and background sequences, including
`38;2` and `48;2`. The capture harness verifies those sequences and verifies
the live PTY size before it exits.

## Ordered interaction

| Image | Input since the preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-report-building.png` | Launch the exact command | Automatic Compare wait opens on the result-free Meld report topology; `R/r` has one stable meaning from the first frame | None from Meld; only isolated fixture setup predates this screen |
| `02-context-browser.png` | `c` | The switch-shaped readable namespace marks the unrelated Task 3 current Context while remaining unable to switch it | None |
| `03-frozen-a-b-c.png` | `i` | Confirmed inputs show frozen A, B, and result C; C explicitly says `UNCHANGED WHILE COMPARE RUNS` | None |
| `04-report-restored.png` | `r` | The animated, result-free report returns directly without toggling through another surface | None |
| `05-seeded-review.png` | Provider returns | The saved Compare report seeds the symmetric Meld review; result C is the current save location and has zero proposed Memories | Exact ordered Compare basis, empty result Context, and target-bound Meld session are published |
| `06-required-issue.png` | `Tab`, `Down`, `Enter` | The required compensation conflict opens with both exact source claims and proposed resolutions | None |
| `07-staged-response.png` | `Tab`, `Enter` | `Keep all supported terms` is visibly checked; To Do offers `REVIEW AND APPLY` but says nothing changes before review | None; selection is process-local and not incorporated or applied |
| `08-close-receipt.png` | `q` | Stable CLI snapshot confirms `AWAITING_REPLY`, one open required issue, zero results, and the imported Compare ID | None |
| `09-read-only-verification.png` | `v`, `Enter` at the capture gate | Explicit `mem compare --from ... --to ... --snapshot` reuses the basis; `mem status` still shows Task 3 current; `mem show` proves C is empty | None |

The final contract check reports:

- `CURRENT · task-3/local/personal-memory · UNCHANGED`
- `ORDERED COMPARE BASIS · SAVED`
- `COMPARE SCOPE · (True, False)`
- `RESULT C · task-2/participant/proposal-workspace2 · 0 MEMORIES`
- `MELD SESSION · AWAITING_REPLY · NOT APPLIED`

Run `python docs/screenshots/meld-auto-compare-basis-20260810/capture.py`
from the repository root to refresh the complete ordered set. The script
creates and removes only its own temporary fixture store.

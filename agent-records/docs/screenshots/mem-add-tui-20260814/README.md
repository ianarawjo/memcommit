# Add TUI capture log

This ordered set records the first input-and-durable-effect operation built on
the extracted TUI component hierarchy. It uses the real `mem add` Typer route
inside a color-capable PTY and an isolated temporary Store.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/mem-add-tui-20260814/capture.py`
- Command under capture: `mem add`, invoked through the real Typer root with
  `standalone_mode=False` so the child can print post-close durable evidence
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated local fixture; current `target`, peer
  `alpha`; host Profiles and Grants are excluded from the fixture
- PTY: `180` columns × `52` rows; the child verifies the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR`
  unset, and command-attempt logging disabled
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full Menlo canvas; raw `.typescript` and plain `.txt` evidence remain
  beside every PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry.png` | Launch `mem add` | Shared Context selector, one empty draft, and exact To Do effect; draft surface owns initial focus | None |
| `02-alpha-target-selected.png` | `Shift-Tab`, `Up`, `Enter` | Shared Context selector stages `alpha` while `target` remains the global current Context | None |
| `03-first-multiline-edit.png` | `Tab`, `E`, two lines separated by `Enter` | In-frame common multiline editor retains a physical newline | None |
| `04-first-draft-staged.png` | `Ctrl-S` | First Memory is saved only to the process-local draft batch | None |
| `05-second-editor-scrolled.png` | `N`, twelve physical lines | The shared writable multiline component scrolls to keep the editor cursor visible | None |
| `06-two-drafts-staged.png` | `Ctrl-S` | Two independently editable exact Memories are staged | None |
| `07-exact-add-action.png` | `Tab` | To Do owns focus and shows the one atomic checkpoint effect | None |
| `08-success-receipt.png` | `Enter` | Both draft rows carry durable Memory UIDs and the receipt reports one checkpoint | Two Memories and one Add checkpoint in `alpha` |
| `09-durable-verification.png` | `Enter` | Full-screen TUI closes; direct Store verification prints both exact multiline contents, no Memory in `target`, and exactly one Add checkpoint | No additional mutation |
| `10-cancel-verification.png` | Separate launch, `Q` | Post-close verification confirms zero Memories and no Add checkpoint | None |

The editable field uses prompt-toolkit's buffer-owned cursor and scrolling.
The read-only draft viewport, Context navigation, cross-frame focus movement,
and in-frame input attachment are separate shared components. The Add screen
does not manipulate `vertical_scroll` or duplicate tree/focus indices.

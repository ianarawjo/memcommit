# Continuous Remove session

GUI automation was unavailable, so `capture.py` rendered the actual
color-preserving byte stream from a real zsh PTY. The capture used 180 columns
by 52 rows, set `TERM=xterm-256color` and `COLORTERM=truecolor`, explicitly
removed `NO_COLOR`, and verified the live dimensions before accepting the
screenshots. The child process redirected the real CLI to a temporary Store;
the active Profile Store was neither read nor mutated.

Common state:

- Repository: `/Users/KimMunyeong/Github/memcommit`
- Exact command: `mem remove`
- PTY: 180 columns × 52 rows
- Profile: isolated temporary Store; no Grant routing
- Current Context: `curation/inbox`
- Starting Memories: `11111111` expired draft, `22222222` duplicate note,
  `33333333` reviewed summary

| Image | Preceding keys | Visible state | Durable effect |
|---|---|---|---|
| `01-session-entry.png` | none after `mem remove` | Current Context focused; all three direct Memories visible; footer says `Esc/q close` | None |
| `02-first-item-focused.png` | `Down` | Exact `11111111` Memory is the Enter target | None |
| `03-first-removed-next-focused.png` | `Enter` | The same picker canvas removes `11111111`, focuses `22222222`, and shows the `REMOVED` action plus removed Memory description in red only in the footer | One `remove` checkpoint commits deletion of `11111111` |
| `04-second-removed-next-focused.png` | `Enter` | The same picker canvas removes `22222222`, focuses surviving `33333333`, and replaces the red footer receipt | A second independent `remove` checkpoint commits deletion of `22222222` |
| `05-esc-close-receipts.png` | `Escape` | The session is closed; `remove → remove` and the final durable count verify the two prior footer receipts | None; Escape does not apply, roll back, or group prior deletions |
| `06-read-only-verification.png` | `Enter` at the capture pause | `mem show --context curation/inbox` displays only `33333333` | None; read-only verification |

The capture script verifies that the raw stream enters and leaves the terminal's
alternate screen exactly once. It also rejects any separate normal-buffer
`Removed` receipt, checks the footer's semantic remove color, and confirms that
the isolated Store retains two newest `remove` checkpoints rather than one
session-wide checkpoint.

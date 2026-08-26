# Shared `Ctrl-C` cancellation capture log

This ordered color-PTY record verifies that `Ctrl-C` immediately leaves each
affected TUI without freezing a request or mutating the disposable Store. It
also records the corrected `mem help` close-key guidance.

## Reproduction frame

- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, set and verified before every launch
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile: disposable authoring fixture
- Current Context: `beta`
- Fixture: `alpha`, `beta`, and `beta/child`; four total Memories
- Durable scope: cancellation only; the complete disposable Store is
  byte-hashed immediately before and after each TUI

The capture command is:

```bash
env -u NO_COLOR TERM=xterm-256color COLORTERM=truecolor \
  python agent-records/screenshots/tui-interrupt-cancel-20260822/capture.py
```

## Ordered interaction

| Images | Exact command and preceding input | Visible states | Durable mutation |
| --- | --- | --- | --- |
| `01`–`02` | `mem add`; then `Ctrl-C` | Add entry; returned command plus Store/list verification | None |
| `03`–`04` | `mem edit`; then `Ctrl-C` | Edit entry; returned command plus Store/list verification | None |
| `05`–`06` | `mem embed`; then `Ctrl-C` | Embed entry; returned command plus Store/list verification | None |
| `07`–`08` | `mem reference`; then `Ctrl-C` | Reference entry; returned command plus Store/list verification | None |
| `09`–`10` | `mem atomize --sessions`; `Enter` on Add new, then `Ctrl-C` | New Atomize endpoint setup; cancellation receipt plus Store/list verification | None |
| `11`–`12` | `mem help`; then `Ctrl-C` | Help entry with `Q/Esc close`; returned command plus Store/list verification | None |

Every cancellation image contains `CTRL-C CLOSED THE ACTIVE TUI · YES` and
`COMPLETE STORE UNCHANGED · YES`, followed by the actual output of
`mem show --context beta`.

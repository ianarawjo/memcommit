# Summarize immediate-routing capture log

This ordered set verifies that ordinary Summarize invocations are complete
execution requests, while the broader Recent/Context/range workbench remains
available through explicit `--tui`.

## Reproduction frame

- Command: `python docs/screenshots/mem-summarize-immediate-routing-20260821/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, `TERM=xterm-256color`,
  `COLORTERM=truecolor`, and `NO_COLOR` unset
- Fixture: isolated empty Contexts `route/current` and `practice/source`, with
  `route/current` as the command-start current Context
- Provider boundary: empty summary frames make every captured route
  provider-free
- Persistence boundary: command-attempt logging is disabled and every Store
  file is byte-compared before and after each command

## Ordered interaction

| Image | Exact command / input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-current-default-immediate.png` | `mem summarize` | The direct Summary for command-start current Context `route/current` prints immediately without an alternate-screen setup | None |
| `02-explicit-context-immediate.png` | `mem summarize practice/source` | The explicitly named direct Summary prints immediately without a second Run action | None |
| `03-explicit-tui-setup.png` | `mem summarize practice/source --tui` | The optional Context/range/Summary workbench opens with `practice/source` staged and no execution yet | None |
| `04-explicit-tui-cancel-verification.png` | `q` | The TUI closes, reports cancellation, and verifies unchanged Context bytes and current pointer | None |

The capture script asserts that the two ordinary commands never enter the
alternate screen. It separately verifies foreground/background ANSI styles for
the explicitly requested TUI and retains raw `.typescript`, terminal-text
`.txt`, and full `180×52` `.png` artifacts for every state.

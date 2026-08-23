# Lightweight Compare summary PTY trace

This ordered trace executes the actual CLI callback and application boundary
for the new default Compare contract. The provider is a deterministic
source-linked capture double so the terminal states are reproducible; a
separate live Codex/none run over 52 Memories completed in 7.87 seconds after
the single-paragraph contract replaced the earlier sectioned response.

- PTY: `180` columns × `52` rows, set by `pexpect` and reported by the child.
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, with `NO_COLOR` removed. The raw
  typescript set is checked for true-color ANSI.
- Profile: isolated explicit Store; current Context `capture/reference`.
- Command: `mem compare capture/reference capture/peer`.
- Policy receipt: production, Codex `gpt-5.6-sol`, reasoning `none`, 600-second
  timeout.

| Image | State and preceding input | Durable mutation |
| --- | --- | --- |
| `01-provider-wait.png` | explicit Reference and Peer are frozen; the shared interactive wait shell shows summary inference | none |
| `02-transient-summary-result.png` | provider returned exactly one bounded source-linked prose paragraph; output returned to the caller with no resident result screen | none |
| `03-read-only-verification.png` | `V`; exact source digests unchanged, one provider call, zero checkpoints, no deep analysis, current Context unchanged | none |

The explicit operands are the Source/peer selection for this representative
path. Bare setup selection is independently captured in
`../semantic-bare-entry-routing-20260822/01-compare-bare-new-setup.png`; this
focused set starts at the reviewed explicit command so it does not duplicate
unchanged setup mechanics.

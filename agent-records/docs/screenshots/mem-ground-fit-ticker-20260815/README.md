# Incremental ticker Ground Fit

This directory records one real `gpt-5.6-sol` / `none` evaluation in an
isolated temporary MemCommit store. It imports the five Rules from the earlier
real ticker Distill receipt, adds each concrete Example as its own Ground
revision, and retains every Fit run as an immutable read-only receipt.

Command:

```bash
python agent-records/docs/screenshots/mem-ground-fit-ticker-20260815/capture.py
```

The capture runs in a `180 × 52` color-capable PTY with `TERM=xterm-256color`,
`COLORTERM=truecolor`, and `NO_COLOR` removed. Each PNG is rendered from the
actual ANSI PTY stream; the adjacent `.txt` and `.typescript` files retain its
plain and color-preserving forms.

| # | File | Preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| 01 | `01-ground-rules-and-18-examples.png` | entry | v3 Ground after five one-at-a-time Rule additions and eighteen one-at-a-time Example additions | 23 Ground revisions |
| 02 | `02-first-fit-running.png` | `R` | first provider turn, no receipt yet | none |
| 03 | `03-first-fit-receipt.png` | provider completion | immutable Fit receipt for Examples 1–18 | one Fit receipt |
| 04 | `04-example-19-stales-fit.png` | `N` | Axiom Example added; selected v3 proposition card shows prior receipt stale | one Ground revision |
| 05 | `05-second-fit-running.png` | `R` | second provider turn, no new receipt yet | none |
| 06 | `06-fit-after-example-19.png` | provider completion | actual Fit relation after the Axiom Example; the three underspecified single-word mappings remain visible | one Fit receipt |
| 07 | `07-revisions-stale-fit.png` | `N` | Rules 2 and 3 refined and Example 20 added; prior receipt stale | three Ground revisions |
| 08 | `08-final-fit-running.png` | `R` | final provider turn over all 20 Examples | none |
| 09 | `09-final-fit-receipt.png` | provider completion | immutable final Fit receipt | one Fit receipt |
| 10 | `10-verification.png` | `V` | revision, count, freshness, and non-mutation checks | none |

`actual-run.json` contains the exact Ground revision ledger, all three
provider-backed reports, provider identity, receipt freshness checks, and the
final Ground digest. The isolated store is removed after capture; no user
Profile Context or Ground is changed.

Actual result: the first 18-Example run returned `FIT 15` and
`UNDERDETERMINED 3`; Redwood, Meridian, and Solstice exposed that “concise
three-letter mnemonic” did not specify a deterministic character-selection
algorithm. Adding Axiom as Example 19 made the previous receipt stale and the
next run returned `FIT 16 / UNDERDETERMINED 3`; Axiom itself fit the combined
initial-per-word Rules. After clarifying Rule 2, making Rule 3 explicitly use
the first three alphabetic characters, and adding Example 20, the final
revision returned `FIT 20` and its receipt was current.

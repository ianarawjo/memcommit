# Resolve automatic-interpretation terminal evidence

## Capture contract

- Capture command: `python agent-records/screenshots/mem-resolve-automatic-interpretation-20260820/capture.py`
- Repository: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns by `52` rows, verified inside every child process
- Color environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Store: a fresh isolated temporary `.mem` root per scenario
- Current Context: `resolve/capture`
- Provider: deterministic in-process fixture crossing the production Fit,
  Issue decoder, verifier, final Fit, application, CLI, and TUI paths; no
  network provider or cache is used
- Artifacts: every numbered state has a rendered PNG, plain-text canvas, and
  color-preserving raw PTY typescript. The capture asserts foreground and
  background ANSI styles before succeeding.

## Ordered interaction log

| # | State | Preceding keys or action | Visible contract | Durable effect at this step |
| --- | --- | --- | --- | --- |
| 01 | Automatic success receipt | Run `mem resolve --context resolve/capture --tui` | The grounded unique exact-schedule plan applies without a candidate-choice or approval screen; receipt reports two UPDATEs and one checkpoint | One Resolve checkpoint committed |
| 02 | Store verification | `Enter` | Direct Store reload shows exact weekday/weekend Memories and exactly one `resolve` checkpoint | None beyond 01 |
| 03 | Assumed working view | Fresh fixture whose verifier finds one explicit unsupported premise | `ASSUMED`, Issue assumption, and proposed effect appear in a read-only Viewer with no Apply | None |
| 04 | Assumed verification | `Q`, then `Enter` | Original Memories remain and no checkpoint exists | None |
| 05 | Already-Fit outcome | Fresh fixture whose initial complete Fit is YES | Read-only terminal outcome exposes no plan or Apply | None |
| 06 | Already-Fit verification | `Q`, then `Enter` | Original Memories remain and no checkpoint exists | None |
| 07 | Stale automatic Apply failure | Fresh grounded plan; inject a concurrent Memory immediately before Apply | Frozen digest failure is printed; Resolve publishes no partial effect | Test injection changes Context; Resolve publishes nothing |
| 08 | Stale verification | `Enter` | Concurrent note is present, automatic CREATE is absent, and there is no `resolve` checkpoint | None beyond injected change |

## Reproduction notes

The script drives the real Typer Resolve command through `pexpect`; it does not
synthesize a screen. Grounded execution is line-oriented because it applies
automatically, while `ASSUMED` and `ALREADY_FIT` use the read-only Viewer. The
fixture is local only for deterministic reproduction. Actual
configured-provider trials are recorded in
`agent-records/resolve-fit-repair-design-rationale.md`: grounded UPDATE,
explicit DELETE, `ASSUMED`, `ALREADY_FIT`, rule STOP, and cardinality fail-closed paths
were exercised against isolated temporary Stores.

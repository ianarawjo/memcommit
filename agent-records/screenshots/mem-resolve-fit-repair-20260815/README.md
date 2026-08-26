# Resolve Fit-repair terminal evidence

## Capture contract

- Capture command: `python agent-records/screenshots/mem-resolve-fit-repair-20260815/capture.py`
- Repository: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns by `52` rows, verified inside every child process
- Color environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Store: a fresh isolated temporary `.mem` root per scenario
- Current Context: `resolve/capture`
- Provider: deterministic in-process semantic fixture exercising the real Fit,
  candidate decoder, independent verifier, Pareto comparison, application,
  CLI, and TUI paths; no network provider or cache is used
- Artifacts: each numbered state has a rendered PNG, plain-text canvas, and
  color-preserving raw PTY typescript. Capture asserts ANSI foreground and
  background styles before succeeding.

## Ordered interaction log

| # | State | Preceding keys or action | Visible contract | Durable effect at this step |
| --- | --- | --- | --- | --- |
| 01 | Complete analysis entry | Run `mem resolve --context resolve/capture --allow-create --tui` | Complete initial non-Fit frame, two independently verified Pareto-incomparable candidates, exact revision | None |
| 02 | Candidate detail | `Tab`, `Enter` | Required Resolve plan opens with source-linked before/after evidence and independent verification | None |
| 03 | Candidate Responses | `Tab` | UPDATE and CREATE are distinct real choices; no fabricated custom option | None |
| 04 | UPDATE selected | `Enter` | One exact candidate hash is checked while both candidates remain inspectable | None |
| 05 | Ready for review | `Tab`, `Tab` | Required item is complete; To Do exposes a separate final review | None |
| 06 | Exact command review | `Enter` | Canonical Context, `--allow-create`, full candidate hash, frozen revision, exact UPDATE, Fit YES, one checkpoint, and Undo recovery | None |
| 07 | Success receipt | `Enter` | Success names the candidate and checkpoint and reports one UPDATE | One Resolve checkpoint committed |
| 08 | Read-only Store verification | `Enter` to close receipt | Direct Store reload shows the qualified weekend Memory and exactly one `resolve` checkpoint | None beyond 07 |
| 09 | Already-Fit outcome | Fresh fixture whose initial complete Fit is YES | Shared read-only Viewer exposes no candidate or Apply | None |
| 10 | Already-Fit verification | `Q` | Original Memories remain and no checkpoint exists | None |
| 11 | Cancel verification | Fresh non-Fit fixture; `Q` from analysis | Original Memories remain and no checkpoint exists | None |
| 12 | Stale Apply failure | Fresh non-Fit fixture; open item, select UPDATE, enter exact review and Apply; inject a concurrent Memory before Apply | Apply failure remains visible because the frozen Context digest changed | Test injection changes Context; Resolve publishes nothing |
| 13 | Stale no-Resolve-checkpoint verification | `Q` after failure | Concurrent note is visible, selected UPDATE is absent, and no `resolve` checkpoint exists | None beyond injected change |

## Reproduction notes

`capture.py` drives the real Typer Resolve command and shared Resolution
Workbench through `pexpect`. It does not render a synthetic screen. The
deterministic provider is intentionally local so the ordered screenshots can
be reproduced without network variance while still crossing the production
decoder, independent semantic gates, Pareto frontier, exact choice validator,
authority/freshness runtime, and one-checkpoint Apply boundary.

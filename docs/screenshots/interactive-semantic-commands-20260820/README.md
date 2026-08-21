# Interactive semantic commands · 2026-08-20

All images are actual prompt-toolkit PTY renders captured at `180×52` with
`TERM=xterm-256color`, `COLORTERM=truecolor`, 24-bit color enabled, and
`NO_COLOR` removed. The fixtures use local names only and no Profile Grant.
Every child verifies the live terminal size before opening its screen.
The setup fixtures have no persisted Profile; their orientation/current names
are `capture/incoming` for Meld and `capture/source` for Update and Sever. The
Resolution fixtures are process-local and have no global current Context.

| Image | Exact entry command / fixture | Preceding keys | Visible boundary | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-meld-entry` | `mem meld` → New; `capture/incoming`, `capture/baseline`, empty `capture/empty` | none | Meld compact setup entry | none |
| `02-meld-start-command` | same | `Tab×7`, replace C with `capture/result`, `Enter` | rebuilt portable `mem meld … --to …` START command owns focus | none |
| `03-meld-receipt-verification` | same | `Enter` | typed setup receipt; provider/session/Apply not run | none |
| `04-update-entry` | `mem update` → New; `capture/source` → `capture/target` | none | Update shared Endpoint Setup | none |
| `05-update-start-command` | same | `Tab×6` | complete `mem update --from … --to …` START command | none |
| `06-update-receipt-verification` | same | `Enter` | typed setup receipt; provider/session/Apply not run | none |
| `07-sever-entry` | `mem sever` → New; local Source and Criteria | none | stacked Sever setup | none |
| `08-sever-start-command` | same | `Enter`, `Down`, `Enter`, `Enter` | complete `mem sever --source … --criteria … --save-as …` START command | none |
| `09-sever-receipt-verification` | same | `Enter` | typed setup receipt; provider/session/Apply not run | none |
| `10-turn-entry` | saved Update Resolution fixture, revision `capture-revision-1` | none | complete staged report | none |
| `11-turn-response-staged` | same | open change, enter Response, save `Use a narrower claim.` | process-local response changed; command will be rebuilt | none |
| `12-turn-command-reviewed` | same | traverse to To Do, `Enter`, `End` | final review shows complete TURN argv with `--expect-session` | none |
| `13-turn-receipt-verification` | same | `Enter` | typed `SUBMIT_ALL` receipt; fixture verifies final Apply was not run | none |
| `14-final-apply-commandless` | ready Update final-review fixture | `Down` | explicit Apply action with no COMMAND section | none |
| `15-final-apply-cancel-verification` | same | `Escape`, `q` | CLOSE receipt; Apply was not run | none |
| `16-stale-turn-rejected` | `mem update --from capture/source --to capture/target --comment 'Use a narrower claim.' --expect-session 000…` | none | real public command rejects a stale revision before provider connection | none; saved session and target verified unchanged |

The TURN fixture exercises the shared Resolution Session implementation used
by Meld, Update, and Sever. Operation-specific argv builders and stale-revision
rejection are separately covered for all three operations in automated tests.
The Apply images intentionally demonstrate the asymmetric non-goal: public
scripted Apply options still exist, but the TUI's final frozen-state approval
does not repeat an exact command.

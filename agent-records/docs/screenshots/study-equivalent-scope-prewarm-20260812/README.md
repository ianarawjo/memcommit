# Equivalent Study scope prewarm snapshots

This ordered evidence set records the transparent descendant-scope fallback
added after the Task 1 Directional Meld parent-root miss. Every command ran in
a separate temporary copy of the active participant store. Authority-side
Contexts were read through their existing Grants, but no real participant or
authority store was mutated.

All captures use an actual `180 × 52` color-capable PTY. The harness verifies
`stty size` as `52 180`, removes `NO_COLOR`, sets `TERM=xterm-256color`,
`COLORTERM=truecolor`, and `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, and
requires ANSI style bytes before writing each raw `.typescript`, visible
`.txt`, and full-canvas `.png`.

| Capture | Exact command / preceding input | Visible state | Durable mutation in temporary copy |
| --- | --- | --- | --- |
| `01-task1-parent-compare-entry` | `mem compare --from task-1/participant --to task-1/campus-wiki --reference-descendants --compared-descendants` | Complete `75:300` report labeled `EQUIVALENT SCOPE PREWARM` | Rebound Compare saved under the parent frame |
| `02-task1-parent-compare-detail` | `Tab`, `Down`, `Enter` | Source-linked relation evidence | None |
| `03-task1-parent-compare-close` | `Q` | Explicit close receipt | None |
| `04-task1-parent-update-entry` | `mem update --from task-1/participant --to task-1/campus-wiki --source-descendants --target-descendants` | Complete Update Impact and equivalent-scope disclosure | Rebound proposal staged only |
| `05-task1-parent-update-detail` | `Tab`, `Down`, `Enter` | One action's Source and reason | None |
| `06-task1-parent-update-close` | `Q` | Staged-only receipt; target explicitly unchanged | None |
| `07-task1-parent-directional-entry` | `mem meld task-1/participant --left-descendants --into task-1/campus-wiki --right-descendants` | Ready Directional review over the complete Source and baseline | Rebound ready proposal saved only |
| `08-task1-parent-directional-detail` | `Tab`, `Down`, `Enter` | Relation-adjacent Source evidence | None |
| `09-task1-parent-directional-close` | `Q` | `EQUIVALENT SCOPE PREWARM · PROVIDER NOT CALLED` receipt | None |
| `10-task1-directional-source-verification` | `mem show --context task-1/participant/construction-updates` | Original Source root and its seven embedded/authorized Context routes | None; read-only |
| `11-task3-rule-child-compare-entry` | Compare `task-3/local/guardrails` to the exact `.../transmission-guidance/public-guidance` child, both descendant-inclusive | Inverse parent-to-child alias is a durable equivalent-scope report | Rebound Compare saved under the child frame |
| `12-task3-rule-child-compare-close` | `Q` | Explicit close receipt | None |
| `13-task3-rule-child-symmetric-meld-entry` | Symmetric Meld of `task-3/local/guardrails` with the exact `public-guidance` child, both descendant-inclusive | Durable equivalent Compare basis opens Meld with no provider call | Empty result and review session created |
| `14-task3-rule-child-symmetric-meld-detail` | `Tab`, `Down`, `Enter` | Relation-adjacent Source claims from both rule frames | None |
| `15-task3-rule-child-symmetric-meld-close` | `Q` | Unapplied `AWAITING_REPLY` snapshot | None |
| `16-task3-rule-child-result-verification` | `mem show --context task-3/participant/rule-child-equivalent-result` | Empty result remains unchanged | None; read-only |
| `17-wrapper-memory-live-miss` | Task 1 parent Directional command after adding one capture-only parent Memory | Equivalent lookup rejected; injected provider stopper proves the live branch was selected | None; no Meld session or provider call |

The final failure uses a local capture-only provider stopper after the command
selects its live path. It does not simulate a cache hit: the added parent
Memory is deliberately outside the prepared owner ledger, so the ordinary
provider route is required and no partial proposal is published.

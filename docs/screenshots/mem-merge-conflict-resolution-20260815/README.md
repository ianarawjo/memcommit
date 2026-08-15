# Conflict-aware Merge terminal evidence

## Capture contract

- Capture command: `python docs/screenshots/mem-merge-conflict-resolution-20260815/capture.py`
- Repository: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns by `52` rows, verified inside every child process
- Color environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Store: a fresh isolated temporary `.mem` root per scenario
- Current Context: `target`
- Provider/cache: not used; Merge remains deterministic and provider-free
- Artifacts: each numbered state has a rendered PNG, a plain-text canvas, and
  the color-preserving raw PTY typescript. The capture asserts ANSI foreground
  and background styles before succeeding.

## Ordered interaction log

| # | State | Preceding keys or action | Visible contract | Durable effect at this step |
| --- | --- | --- | --- | --- |
| 01 | Direct conflict report | Start bare `mem merge`; `Tab`, `Enter` | Complete frozen direct plan; one required divergence; Apply unavailable | None |
| 02 | Direct conflict detail | `Tab`, `Enter` | Mapping-qualified conflict detail with Target, Source, reason, and deterministic diff | None |
| 03 | Direct Responses | `Tab` | Two real deterministic choices; no custom response | None |
| 04 | Direct choice selected | `Enter` | `KEEP TARGET` checked while the conflict remains inspectable | None |
| 05 | Direct choice cleared | `Enter` | The checked choice clears and Apply becomes unavailable again | None |
| 06 | Direct ready to review | `Enter`, `Tab`, `Tab` | Required count is complete; To Do offers a separate final review | None |
| 07 | Direct final review | `Enter` | Exact argv, full effect boundary, decision counts, and one Apply approval | None |
| 08 | Direct success receipt | `Enter` | Durable receipt with Source, Target, range, counts, checkpoint, and recovery | Direct Merge committed as one command unit |
| 09 | Direct read-only verification | `Enter` to close receipt | Target contains the Source-only addition while the selected Target revision remains | None beyond 08 |
| 10 | Bulk Keep whole-set review | Fresh direct fixture; `Tab`, `Tab`, `K` | Fused `KEEP ALL TARGET` review shows exact argv and whole-set effects before Apply | None |
| 11 | Bulk success receipt | `Enter` | One reviewed bulk decision is materialized with a durable receipt | Direct Merge committed as one command unit |
| 12 | Recursive multi-mapping conflicts | Fresh recursive fixture; choose descendants; continue | Three path-aligned mappings, two required conflicts, and one Source-only Target path | None |
| 13 | Recursive Take Source bulk review | `Tab`, `Tab`, `S` | Fused `TAKE ALL SOURCE` review names recursive reach, creations, replacements, and recovery | None |
| 14 | Recursive success receipt | `Enter` | One receipt covers every mapping, created Context, resolution, and checkpoint | Complete recursive Merge committed atomically |
| 15 | Recursive applied verification | `Enter` to close receipt | Root/child replacements and the new descendant are all present | None beyond 14 |
| 16 | Recursive operation Undo | `Enter` after verification; run `mem undo` | One Undo reports all three affected Context mappings; created descendant is absent | Entire recursive command unit undone |
| 17 | Recursive operation Redo | `Enter`; run `mem redo` | One Redo restores root, child, created path, and checkpointed operation | Entire recursive command unit restored |
| 18 | Conflict cancellation verification | Fresh direct fixture; open Resolution; `Q` | Target retains its pre-Merge revision and has no checkpoint | None |
| 19 | Stale-plan failure | Fresh direct fixture; `Tab`, `Tab`, `K`, `Enter`; mutate Source immediately before Apply | Apply fails visibly because the frozen Source changed | Test injection changes Source; Target publishes nothing |
| 20 | Stale no-partial Target | `Q` after failure | Target still has only its original revision and zero checkpoints | None beyond injected Source change |
| 21 | No-op frozen classification | Fresh identical direct fixture; continue | One item classified `UNCHANGED`; no conflicts or additions | None |
| 22 | No-op success receipt | `Tab`, `Enter` | Explicit `NO TARGET CHANGE` success receipt and recovery boundary | No Target content delta; one verified command checkpoint recorded |
| 23 | No-op read-only verification | `Enter` to close receipt | Target remains identical and the no-op checkpoint is visible | None beyond 22 |
| 24 | Protected Memory choices | Fresh divergent fixture with the Target Memory locked; open conflict Responses | Only `KEEP TARGET` is offered; `TAKE SOURCE` and its bulk shortcut are absent before review | None |
| 25 | Protected Context pre-review failure | Fresh addition fixture with the Target Context locked; continue from setup | Planning fails visibly before a frozen Apply screen can promise the unconditional addition | None |

## Reproduction notes

`capture.py` drives the real Typer Merge command through `pexpect`; it does not
render fixture text. The stale scenario deliberately changes the Source after
review to prove that application revalidates the frozen boundary and publishes
no partial Target state. The no-op scenario deliberately retains a checkpoint
so a verified Merge remains distinguishable from a command that never ran.

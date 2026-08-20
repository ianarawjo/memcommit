# Inline Merge conflict terminal evidence

## Capture contract

- Capture command: `python docs/screenshots/mem-merge-compact-conflict-resolution-20260820/capture.py`
- Repository: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns by `52` rows, verified inside every child process
- Color environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed
- Store: a fresh isolated temporary `.mem` root per scenario
- Profile/current Context: local default Profile; `target` is current
- Provider/cache: unused; Merge remains deterministic and provider-free
- Provenance: every PNG renders the actual color-preserving PTY byte stream;
  every state also retains its raw typescript and plain terminal canvas.

## Ordered interaction log

| # | State | Preceding keys or action | Visible contract | Durable effect |
| --- | --- | --- | --- | --- |
| 01 | Inline conflict entry | Start bare `mem merge`; Source is `source`, Target is current `target`; `Tab`, `Tab`, `Tab`, `Enter` | Complete Source and Target values are inline; Target is checked; the derived Bulk Decision checks `KEEP ALL TARGET`; Apply is ready from entry | None |
| 02 | Source selected | `Left` on conflict 1 | The checked marker moves immediately to Source; because the one-row set is now uniformly Source, the Bulk Decision automatically checks `TAKE ALL SOURCE` | None |
| 03 | Target restored | `Right` | The checked marker and derived whole-set light return to Target | None |
| 04 | Apply ready focused | `Tab` | One frame transition reaches Apply without traversing conflict rows; focus alone does not change a decision | None |
| 05 | Exact whole-set review | `Enter` | The uniform Target set normalizes to exact `--keep-target-all`; Review remains read-only above the separate Controls frame | None |
| 06 | Success receipt | `Enter` | Receipt separates new items, already-present items, kept Target, took Source, whether Target changed, and checkpoint count | Direct Merge committed as one command unit |
| 07 | Direct read-only verification | `Enter` to close | Target retained its conflicting wording, received the Source-only addition, and has one checkpoint | None beyond 06 |
| 08 | Multiple-conflict entry | Fresh recursive fixture; select recursive mode and continue | Two conflicts are simultaneously visible; both start checked on Target; the Target bulk light and Apply are ready | None |
| 09 | Mixed individual choices | `Left`, `Down` | Conflict 1 is Source while conflict 2 remains Target; neither bulk side is checked | None |
| 10 | Take-all Source focused | `Down`, `Right` | The Controls frame labels `BULK DECISION` separately from Apply; moving its cursor does not falsely check a mixed set | None |
| 11 | Bulk staged and Apply ready | `Enter` | Both conflicts are visibly checked on Source, the Source bulk light turns on, and focus moves to Apply | None |
| 12 | Bulk exact review | `Enter` | Exact argv uses `--take-source-all` for the frozen whole set | None |
| 13 | Recursive success receipt | `Enter` | One receipt covers two Source decisions, the created descendant, and three checkpoints | Recursive Merge committed atomically |
| 14 | Recursive read-only verification | `Enter` to close | Root uses Source wording; child and new descendant exist | None beyond 13 |
| 15 | Stale Apply failure | Fresh fixture; `Tab`, `Enter`, `Enter`; inject Source mutation immediately before Apply | Failure remains visible instead of publishing a success receipt | Injection changes Source; Target unchanged |
| 16 | Stale no-partial verification | `Q` | Target retains its prior revision and has zero checkpoints | None beyond injected Source change |
| 17 | Protected Memory capability | Fresh protected fixture | Complete Source evidence stays visible with `×`; Target remains checked; Take-all Source is absent | None |
| 18 | Cancel verification | Fresh fixture; `Q` from entry | Target remains unchanged and has zero checkpoints | None |
| 19 | Long Memory start | Fresh 60-line-per-side fixture | The viewport begins at `SOURCE START`; no body is shortened or ellipsized | None |
| 20 | Long Memory boundary | `PageDown` | Reading continues through `SOURCE END ≠ TARGET START` | None |
| 21 | Long Memory end | `PageDown`, `PageDown` | Reading reaches `target complete line 60` and `TARGET END`; fixed Controls remain independent of the complete comparison viewport | None |
| 22 | Zero-delta kept-Target receipt | Run `mem merge source --keep-target-all` against one divergent shared UID and no additions | Plain output says `NEW 0`, `KEPT TARGET 1`, and `TARGET CHANGED NO` instead of “added nothing new” | One explanatory checkpoint recorded; Target content unchanged |
| 23 | Zero-delta provenance verification | Continue after receipt | Target still contains its prior revision and the checkpoint description records `kept Target 1; took Source 0` | None beyond 22 |

The former Viewer-free compact snapshots in this directory described a
conflict-open/choice-card topology. This refreshed set supersedes that
presentation with one inline Source/Target list while preserving frozen-plan,
exact-review, capability, stale-plan, cancellation, and atomicity boundaries.

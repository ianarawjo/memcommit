# Merge direct and recursive TUI capture log

> Historical interaction evidence: this set records the explicit frozen-plan
> review that preceded ownership-aware auto-application. Conflict-free local
> plans now skip that duplicate review while retaining checkpointed Undo/Redo;
> see `../mem-merge-decision-free-auto-apply-20260815/`. Granted-authority and
> conflict-bearing plans retain their respective review boundaries.

This ordered set records the public `mem merge` TUI, the unchanged direct
contract, the path-aligned recursive contract, and cancellation. Every launch
uses the real Typer route and Store-backed application in an isolated temporary
Store.

## Reproduction frame

- Command: `python agent-records/screenshots/mem-merge-recursive-tui-20260814/capture.py`
- Command under capture: bare `mem merge`, invoked through its real Typer
  command adapter in an isolated Typer root with `standalone_mode=False` so
  unrelated root-command imports cannot affect the focused capture and the
  child can print post-close Store evidence
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: isolated local fixture; current Target `target`,
  readable Source tree `source` and `source/child`, plus Target-only
  `target/preserved`; host Profiles and Grants are excluded
- PTY: `180` columns × `52` rows; each child prints the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset,
  and command-attempt logging disabled
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full Menlo canvas; raw `.typescript` and plain `.txt` evidence remain
  beside every PNG

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-direct-entry.png` | Launch bare `mem merge` | Rebuilt endpoint setup shows coupled direct/recursive shapes, readable A Source with initial focus, and visible frozen B current Target | None |
| `01a-direct-setup-ready.png` | `Tab` | Setup-only To Do owns focus and explicitly offers continuation to frozen-plan review | None |
| `01b-direct-frozen-plan.png` | `Enter` | Separate Viewer shows the complete frozen direct mapping, existing Target state, exact addition identity, and checkpoint count | None |
| `02-direct-exact-command.png` | `Tab` | Exact frozen-plan review shows `mem merge source --direct`, actual plan counts, revalidation, and atomic publication boundary | None |
| `03-direct-success.png` | `Enter` | Success receipt reports direct reach, one Context and one checkpoint | Source root Memory added to `target` |
| `04-direct-verification.png` | `Enter` | TUI closes; Store verification confirms root copied, no `target/child`, Target-only descendant preserved, and one root checkpoint | No additional mutation |
| `05-recursive-range.png` | Separate launch, `Shift-Tab`, `Right` | Operation Shape owns focus with the coupled `RECURSIVE · A/** → B/**` mode selected | None |
| `05a-recursive-setup-ready.png` | `Tab`, `Tab` | Setup-only receipt fixes Source A, current Target B, and recursive mode before planning | None |
| `05b-recursive-frozen-plan.png` | `Enter` | Viewer exposes both path-aligned mappings, including `target/child` as `WILL CREATE`, before Apply | None |
| `06-recursive-exact-command.png` | `Tab` | Exact frozen-plan review shows `--recursive`, two mappings, one creation, two additions, and two checkpoints | None |
| `07-recursive-success.png` | `Enter` | Success receipt reports descendant reach, two Contexts, one created, and two checkpoints | Root updated and `target/child` created atomically |
| `08-recursive-verification.png` | `Enter` | Store verification confirms root and child copied, Target-only descendant preserved, and the root checkpoint present | No additional mutation |
| `09-cancel-verification.png` | Separate setup launch, `Q` | Cancelling before request construction leaves neither copied data nor a checkpoint | None |
| `09a-plan-cancel-verification.png` | Separate launch, `Tab`, `Enter`, then `Q` in frozen-plan Viewer | Cancelling after complete plan preparation still leaves neither copied data nor a checkpoint | None |
| `10-merge-help-detail.png` | Separate `mem help`; `Tab` three times, `Down` nine times, `Right`, then `Down` twice | Analyze & Transform exposes one Merge record with typed direct and recursive Forms plus deterministic Flow, Effect, and Range | None |
| `11-failure-before-persistence.png` | Separate launch through setup and frozen review; the capture port raises at exact Apply before persistence | Frozen-plan review stays open with an explicit Merge failure and no success receipt | None |
| `12-failure-verification.png` | `Q` | CLI preserves the failure as exit 1, then Store verification confirms neither root nor child was copied and no checkpoint exists | None |

Direct and recursive execution share one typed application boundary. The first
TUI returns only a Source/Target/reach request. `prepare_merge()` then creates a
complete read-only plan for the second Viewer, and exact Apply passes that same
plan to the application. Neither screen implements Store mutation or calls the
CLI as a subprocess.

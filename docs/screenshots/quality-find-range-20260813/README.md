# Quality Find aggregate-range setup capture log

This ordered set records the shared flagless setup used by `mem
find-duplicates`, `mem find-ambiguities`, and `mem find-conflicts`. Duplicate
is the representative command because all three use the same target, scope,
approval, cancellation, and read-only boundaries; only the operation label and
the already-existing result adapter differ.

## Reproduction frame

- Command: `python docs/screenshots/quality-find-range-20260813/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: no store is opened; the child uses a synthetic
  readable catalog and a process-local `study/policy` current marker
- PTY: `180` columns × `52` rows; the child prints and verifies the live size
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` and drawn
  at the full `1832×1124` Menlo canvas. Raw `.typescript` and plain `.txt`
  evidence are retained beside every PNG.
- Color verification: the capture requires ANSI foreground and focused-control
  background styles before succeeding.
- Mutation boundary: this capture runs the production setup control but does
  not load a store, connect a provider, execute a finder, create an artifact,
  or mutate a Context.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-entry-current-target.png` | Launch `FIND DUPLICATES` setup | `MULTIPLE TARGETS` and `THIS CONTEXT ONLY` are visible; current `study/policy` is checked | None |
| `02-multiple-independent-targets.png` | `Down`, `Enter` | `study/operations` joins the checked set without clearing `study/policy` | None |
| `03-multiple-target-setting.png` | `Tab` | Scope owns focus and visibly confirms `MULTIPLE TARGETS` | None |
| `04-include-descendants-setting.png` | `Down`, `Right` | `INCLUDE DESCENDANTS` is selected and the effective count becomes three | None |
| `05-effective-descendant-visible.png` | `Shift-Tab`, `Up`, `Right` | Expanding `study/policy` shows its implied descendant `study/policy/archive` checked | None |
| `06-exact-run-review.png` | `Tab`, `Tab` | `TO DO` shows the exact finder and three-Context aggregate breadth before execution | None |
| `07-approved-range-receipt.png` | `Enter` | The typed receipt prints roots, effective Contexts, cardinality, and reach | None |
| `08-read-only-verification.png` | `Enter` | Verification confirms setup created no Context, checkpoint, artifact, or provider connection | None |

The approved effective set is `study/policy`, `study/policy/archive`, and
`study/operations`. Execution code consumes that exact set and does not apply
another hidden descendant expansion.

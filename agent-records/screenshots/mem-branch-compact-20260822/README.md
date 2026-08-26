# Compact `mem branch` interaction trace

This ordered set records the migration of bare Branch from two persistent
full-height trees to the shared compact Endpoint Setup. The setup stays in the
terminal main buffer. Source and parent catalogs expand only while their
`BROWSE` control is active, and the concrete Branch command remains visible
before the first durable write.

## Reproduction frame

- Command: `mem branch`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Store: one isolated temporary store for success and one for collision safety
- Profile/Grants: none; only ordinary local fixture Contexts are visible
- Current Context: `practice`
- Success Source: `practice/task-1`, including `practice/task-1/notes`
- Success target: `capture/branch-result`
- Collision target: existing `capture/existing`
- PTY: `180` columns × `52` rows, verified inside each child
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, true-color
  prompt-toolkit depth, and `NO_COLOR` removed
- Renderer: actual cumulative ANSI PTY streams replayed through `pyte` and
  rendered at full terminal resolution with Menlo

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-compact-entry` | launch `mem branch` | two compact endpoint rows; current Source and untouched target suggestion | fixture Contexts only |
| `02-source-browse` | `Right`, `Enter` | complete frozen local Source catalog expanded transiently | none |
| `03-noncurrent-source-selected` | `Down`, `Enter` | `practice/task-1` selected and untouched TO suggestion inherited from A | none |
| `04-descendant-range-selected` | `Right`, `Space` | A explicitly includes lexical descendants | none |
| `05-exact-target-entered` | `Down`, `Ctrl-U`, type `capture/branch-result` | person-owned exact require-new target | none |
| `06-parent-browse` | `Right`, `Enter` | transient parent catalog opened without converting a parent into the target | none |
| `07-edited-target-preserved` | `Down`, `Enter` | parent choice changed; directly edited exact target stayed unchanged | none |
| `08-exact-apply-review` | `Down` | complete `mem branch ... --from ... --source-descendants` command focused | none |
| `09-success-receipt` | `Enter` | two-Context subtree Branch receipt and switched target root | Branch target root and descendant created atomically |
| `10-read-only-result-verification` | `V` | target root/descendant exist, Source bytes unchanged, unrelated Task 2 absent | none after receipt |
| `11-existing-target-blocked` | new flow; `Down`, replace TO with `capture/existing`, `Down` | exact command remains invalid because TO is already owned durable state | fixture Contexts only |
| `12-collision-read-only-verification` | `Q` | cancellation receipt; existing target bytes, catalog, and current Context unchanged | none |

The success path deliberately chooses a non-current Source so the reviewed
`--from` operand is necessary rather than decorative. The collision path proves
that `BROWSE PARENT` and direct target input cannot repurpose an existing empty
or populated Context. Reproduce from the repository root with:

```sh
python agent-records/screenshots/mem-branch-compact-20260822/capture.py
```

# Study alternative-flow audit

This capture set tests three seemingly plausible lower-level alternatives to
the Study operations: Branch plus Merge for Task 2, batch Add for Task 1, and
Delete for Task 3. All mutations occur under an isolated temporary HOME and a
fresh `init-study` participant/authority pair. The real Profile registry and
Study stores are not opened or changed.

The run uses the installed `mem` entry point against the current source in a
color-capable `180x52` PTY. It removes `NO_COLOR`, sets
`TERM=xterm-256color` and `COLORTERM=truecolor`, and verifies the live terminal
size and ANSI foreground/background styles. The temporary HOME is deleted
after the run.

## Ordered interaction log

| Capture | Command / preceding input | Visible result | Durable effect in temporary Study |
|---|---|---|---|
| `01-task2-branch-source` | `mem branch` | local Task 2 proposal workspace is selected; granted Advisor Contexts are absent | none |
| `02-task2-branch-range` | `Tab` | exact Source range | none |
| `03-task2-branch-destination` | `Tab` | suggested fresh `proposal-workspace/branch` | none |
| `04-task2-branch-apply` | `Tab` | exact reviewed Apply action | none |
| `05-task2-branch-one-receipt` | `Enter` | first local branch created | one new empty local Context |
| `06-task2-second-branch` | switch to base, `mem branch` | collision-free `branch-2` suggestion | none |
| `07-task2-branch-two-receipt` | `Tab` x3, `Enter` | second local branch created | one new empty local Context |
| `08-task2-merge-verification` | merge Advisor 2, then branch 1; `mem status --short` | both merges add nothing; branch 2 has zero Memories | checkpoints only; no Memory added |
| `09-task1-batch-add-receipt` | repeatable `--memory`, CREATE-granted `task-1/campus-wiki` | technical batch Add succeeds | two audit Memories added to granted root |
| `10-task3-delete-entry` | switch to `task-3/local/personal-memory`; `mem delete` | local Context/direct-item picker | none |
| `11-task3-delete-cancel` | `Q` | deletion cancelled | none |
| `12-task3-read-only-verification` | `mem status --short` | root has zero direct Memories and three embedded Contexts | none |

The Task 2 Advisor roots contain their Memories in lexical descendants. Merge
is exact and direct, while Branch accepts ordinary local Sources only. The
tested root-level Branch/Merge sequence is therefore executable but transfers
no Advisor Memory.

Task 1 batch Add is authorized by the campus-wiki CREATE Grant, but one Add
request targets one exact Context and cannot replace existing statements. The
fixture oracle requires 34 modifications and 43 additions distributed across
six descendant targets.

Task 3's local personal-memory corpus contains 333 Memories across 34 direct
Context frames. Delete removes one selected direct item at a time (or an exact
Context while preserving descendants), so it neither curates the complete
frame nor creates the Source-preserving selected output required by the task.

# Study Task 1 agent-driven terminal debug log

## Purpose and evidence boundary

This note records the first agent-driven Task 1 exercise so the workflow can be
repeated without relying on conversation history. The task-solving portions of
the run were black-box CLI exercises:

- use only `mem help`, command `--help`, the Task description, and information
  visibly rendered by the terminal;
- do not inspect fixture source, a solution, or an answer key;
- operate interactive screens by sending literal keyboard input, including
  arrow keys;
- use a TTY for interactive screens and non-TTY output where the command's
  documented behavior calls for it; and
- report and stop at a blocker rather than infer a hidden solution.

The run was performed from the repository root on 2026-08-09. The worktree
already contained unrelated in-progress changes, so this is an observational
debug record, not a clean-baseline benchmark.

The run had three deliberately distinct phases:

1. a black-box Task 1 attempt that stopped at a semantic-execution preflight
   error before provider connection;
2. a source-guided diagnosis and implementation phase, explicitly requested
   after the blocker was reported; and
3. a black-box terminal rerun from the blocked Update through review and
   application.

Only the middle phase inspected implementation code. No answer or scoring
material was consulted in any phase.

The chronological commands, literal keys, recoveries, mistaken attempts, and
observed transitions that can be reconstructed from the first run are retained
in `docs/study-task-1-runs/20260809-first-agent-run.md`. The first run did not
start with a raw PTY byte recorder, so that transcript is intentionally labeled
as a reconstruction rather than a byte-complete capture.

## Study initialization and visible task

`mem init-study` created and selected the isolated participant Profile
`study-20260809T215815Z-03fed00a` with its paired granted-memory authority
Profile. The Task 1 description visibly instructed the participant to use the
verified construction updates to update the affected campus wiki and
contribute the result.

The first interactive `mem update` setup used the following keyboard path:

1. Enter opened the Update setup;
2. Source was `task-1/participant/construction-updates`;
3. Down three times moved to Source `RANGE`, and Right selected
   `INCLUDE DESCENDANTS`;
4. Tab moved to Target;
5. Down selected `task-1`, Right expanded it, Down selected
   `task-1/campus-wiki`, and Enter checked it;
6. Down five times moved to Target `RANGE`, and Right selected
   `INCLUDE DESCENDANTS`; and
7. Tab moved to Apply, then Enter submitted the setup.

The equivalent explicit command used for the later rerun was:

```text
mem update \
  --from task-1/participant/construction-updates \
  --to task-1/campus-wiki \
  --source-descendants \
  --target-descendants
```

Relative names, the current Context pointer, and answer material were not used
to choose the endpoints.

## First-run blocker

The first attempt failed before provider connection with the visible message:

```text
Update error: The source and target Contexts exceed the bounded Update
execution plan. Input is never truncated; staged relation reconciliation is
not yet enabled for a complete replacement plan.
```

This was reported as the stopping point rather than bypassed. Source-guided
diagnosis then measured the frozen workload as:

- Source Contexts: `7`;
- Source Memories: `75`;
- Target Contexts: `7`;
- Target Memories: `300`;
- aggregate input characters: `82,945`;
- then-configured input limit: `200,000`;
- theoretical expected output items: `375`;
- then-configured expected-output limit: `200`; and
- theoretical relation edges: `22,500`.

The failing axis was therefore the synthetic expected-output item count, not
provider input capacity. The provider was never called. The canonical Task 1
workload fit comfortably within both the old character limit and the actual
provider capacity but was rejected by an independent count gate.

## Source-guided semantic-limit change

The requested policy change made `1,000,000` characters the shared aggregate
input contract for the currently supported semantic provider and removed
arbitrary aggregate item, expected-output, and relation-edge rejection gates.
Those counts remain available as planning diagnostics, while provider capacity
is enforced by the character axis.

The audit covered Update, Compare, Meld, selective curation, findings,
Atomize, Atomize Grounding, Search, Find, Translate, history search,
Summarize, and rationale-related provider frames. Structural bounds were not
removed: a schema may still constrain an output to the exact frozen candidate
universe, a directional edit still has one target, and operation-owned semantic
invariants still apply.

The change intentionally did not authorize hidden batching. Operations whose
meaning requires a whole frame still reject a frame larger than the shared
provider capacity, and one oversized Memory is never silently truncated.

The rationale and current limitations are recorded in
`docs/semantic-execution-planning-design-rationale.md`.

## Rerun result

The explicit Update command passed preflight after the change and reached the
provider. It produced one saved staged proposal with the visible summary:

```text
STAGED · 33 EDITS · 42 ADDITIONS · 0 REMOVALS · 75 CHANGES
```

The first provider-backed TTY produced more terminal output than the calling
tool retained, so its PTY session identifier was lost. Read-only recovery
confirmed that the complete proposal had already been saved as `staged`. The
orphaned TUI process was then terminated without changing the saved proposal,
and the same command reopened that proposal without another provider call.

The review exercised these literal navigation paths:

- from the initial Viewer, Tab, Down, Enter opened change `1/75`;
- from an opened detail, Tab twice returned focus to Items, then Down and Enter
  opened change `2/75`;
- from an opened detail, Tab twice returned to Items, then End and Enter opened
  change `75/75`; and
- Backspace returned from a detail to the complete report.

The sampled details included exact Before/After content, reason, owner, Memory
UID, Source Context, Source Memory, and source-content digest. The first two
items were edits and the final item was an addition. End traversed the full
75-item list, so the removed count gate was also exercised by the review UI.

Final application required two distinct steps. Enter on the To Do action opened
the read-only `REVIEW AND APPLY` detail. That transition focused Viewer. From
there, Tab moved to Items, a second Tab moved back to To Do, and Enter applied
the exact staged proposal. The terminal reported:

```text
Applied update: task-1/participant/construction-updates -> task-1/campus-wiki
APPLIED · 33 EDITS · 42 ADDITIONS · 0 REMOVALS · 75 CHANGES
Updated granted authority target task-1/campus-wiki.
The participant source and fixed study baseline were not changed.
```

Running the identical explicit Update again returned the recorded applied
receipt and ended with `This update was already applied locally.`. It did not
call the provider or apply the changes a second time.

## PTY-size and final-action findings

The API-created PTY again defaulted to 80 columns by 24 rows. At that size the
complete report was visible, but opening a change left too little vertical
space for a useful detail: the Responses and Items frames consumed most of the
screen, while Page Up and Up did not reveal the hidden body during this run.

Reopening the saved proposal after:

```text
stty rows 60 cols 180
```

made the complete detail, provenance, Responses, Items, and To Do frames usable.
No responsive-layout code was changed in this exercise. A repeat run should set
the PTY character grid before launching Update and should retain 80-by-24 as a
separate layout-regression case.

The final-action focus transition is also easy to misread. The To Do row says
`Enter to apply now`, but opening it moves focus to Viewer, whose footer says
`Enter return`. Pressing Enter immediately therefore returns without applying.
The reliable path is to read the confirmation, Tab through Items back to To Do,
and then press Enter. This preserved a separate review and application action,
but the visible wording and focus transition deserve a focused usability test.

## Contribution and additional smoke checks

`mem help` listed no separate `contribute` command. It described `share` as
sending an ordinary Context through a grant-backed receiver endpoint. Trying
to use the updated wiki as a Share source produced:

```text
Error: Context 'task-1/campus-wiki' not found.
```

`mem contexts` explained the result: the campus wiki was a granted authority
view with Update and derived-work permissions, not an ordinary local Context.
The successful authority-target Update was the Task 1 contribution path;
sharing that same view again was neither necessary nor valid.

A separate non-TTY, provider-backed read-only check ran:

```text
mem find-conflicts --context task-1/campus-wiki/facility-updates
```

It completed with:

```text
65 direct memories, 2080 pairs, 0 findings
```

This confirmed that another semantic operation could read the updated granted
target and finish without a count-limit or authority error. It did not modify
the Context.

## Verification after the changes

- final focused semantic policy, Update, quality-finder, and Sever tests:
  115 passed;
- the broader relevant semantic suite run during implementation: 378 passed;
- Ruff on the changed semantic files and `git diff --check`: passed; and
- the complete suite reached 2,615 passes, but separate dirty-worktree state
  left 38 failures and 39 errors, mostly because the Task 2 discovery corpus no
  longer matched its frozen calibration lock. Two unrelated failures were an
  Atomize screen-capture mismatch and a merge error-message mismatch.

## Proposed repeat-run method

Use a fresh `mem init-study` Profile for every repetition so an applied receipt
and authority mutations from an earlier run cannot short-circuit the exercise.
Do not reuse the Profile name recorded above.

Drive the black-box portion with a small PTY recorder that:

1. creates the fresh Study Profile and records its exact name;
2. sets an explicit character grid before each interactive launch;
3. timestamps every command, raw frame, normalized readable frame, and key;
4. sends literal sequences such as Down `ESC [ B`, Right `ESC [ C`, Enter
   `CR`, Tab `HT`, Backspace `DEL`, and End `ESC [ F`;
5. records the provider start and completion times without imposing a short
   fixed timeout;
6. stops at any visible preflight, authority, provider, schema, review, or CAS
   error; and
7. does not consult source, fixtures, calibration data, solution material, or
   an answer key during the task-solving phase.

Run at least these layout cases independently:

| PTY columns x rows | Purpose |
|---|---|
| 80x24 | Reproduce the constrained-detail behavior |
| 80x60 | Isolate the benefit of additional rows |
| 180x24 | Confirm whether width alone helps the detail |
| 180x60 | Known working control for the 75-item review |

For a semantic repetition, use only the known working control after the layout
matrix. Preserve the generated proposal and report a blocker before terminating
an inaccessible TUI. After successful application, repeat the identical Update
once to verify the applied-receipt path, then use only read-only smoke checks.

## Repeat-run record convention

Keep the evidence boundary and repeat method above stable. Append one concise
row here for each run, but put a long chronological transcript in a separate
`docs/study-task-1-runs/<UTC timestamp>-<short outcome>.md` note so later runs
do not rewrite or blur the first-run observations.

| Run | Date | Fresh Profile | PTY columns x rows | Outcome | First blocker or notable finding |
|---|---|---|---|---|---|
| 1 | 2026-08-09 | `study-20260809T215815Z-03fed00a` | 80x24, then 180x60 | 75 changes applied | Expected-output count gate rejected an 82,945-character frame before provider connection |
| 2 | 2026-08-10 | `study-20260810T010815Z-meld-a-b` | 120x40 | 6 owner-routed Meld additions applied | Saved-session route hint initially omitted B's `--right-descendants`; execution and storage were correct, and the display route was fixed |

For every added row, record the exact code revision or explicitly say `dirty
worktree`, the provider route, elapsed provider time when observable, proposal
counts, final status, whether the idempotence check passed, and the path to any
raw PTY capture. Record a failed or interrupted run too; do not keep only
successful repetitions.

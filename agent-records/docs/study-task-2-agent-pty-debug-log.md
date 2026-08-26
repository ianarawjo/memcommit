# Study Task 2 agent-driven terminal debug log

## Purpose and evidence boundary

This note records the first agent-driven Task 2 exercise so the workflow can be
repeated without relying on conversation history. The run was a black-box CLI
exercise rather than a source-guided solution:

- use only `mem help` and information visibly rendered by the terminal;
- do not inspect fixture source, a solution, or an answer key;
- operate the TUI by sending literal keyboard input, including arrow keys;
- use a TTY for interactive screens and non-TTY output only when the command's
  documented behavior calls for it; and
- report and stop if the visible interface does not supply enough information
  to continue safely.

The run was performed from the repository root on 2026-08-09. The worktree
already contained unrelated in-progress changes, so this is an observational
debug record, not a clean-baseline benchmark.

## First-run method

The CLI was launched in an API-created pseudo-terminal. Commands and key
sequences were sent incrementally, and each returned terminal frame was read
before choosing the next input. This exercised the same keyboard path as an
interactive terminal, but it did not use a graphical terminal emulator or its
physical display dimensions.

More precisely, the first run used this control path:

1. start a shell command with an allocated PTY rather than ordinary captured
   pipes;
2. inspect the returned terminal frame;
3. send the next command text or literal key bytes to that same live PTY;
4. use terminal escape sequences for arrows and navigation rather than editing
   state through Python or calling command internals;
5. poll the same PTY again after long provider turns; and
6. when the 80×24 Meld setup could not render, leave that attempt, set the next
   PTY to 140×50 with `stty`, and reopen the setup through its visible CLI path.

This was manually agent-steered: the next key was selected after reading each
visible frame. It was not a prerecorded macro, a prompt-toolkit test fixture,
Computer Use against a graphical terminal, or a source-level invocation of TUI
callbacks.

### Trace-completeness boundary

The first run did **not** retain one raw, timestamped transcript containing
every command, screen-control sequence, and key in exact chronological order.
The conversation retained the important command outcomes, blockers, timings,
and specific failed/successful keys, but it is not sufficient to truthfully
reconstruct an exact keystroke-for-keystroke path. The second-run capture must
provide that missing trace instead of filling it with inferred actions.

The Task 2 flow reached completion through Compare and symmetric Meld. The
visible final result reported:

- source coverage: `300/300`;
- relations: `97/97`;
- final Memories: `115`;
- remaining issues: `0`;
- Compare provider time: approximately 223 seconds; and
- Meld incorporation time: approximately 427 seconds.

These values record what the terminal displayed. They are not a reconstruction
from fixtures or answer material.

## PTY-size finding

The API-created PTY starts at 80 columns by 24 rows. A direct measurement
reported all of the following:

```text
stty size        -> 24 80
COLUMNS / LINES  -> 80 / 24
TIOCGWINSZ       -> rows=24 cols=80 xpixel=0 ypixel=0
```

The two common notations use opposite orders:

- `80×24 PTY` means **80 character columns × 24 character rows**;
- `stty size` prints the same size as **rows then columns**, therefore `24 80`;
- `stty cols 140 rows 50` changes it to **140 columns × 50 rows**; and
- this is not a 140-by-50-pixel image.

The host display may be 1920×1080 pixels, but this PTY does not receive those
pixel dimensions: both pixel fields are zero. A terminal emulator normally
derives its character grid from viewport size, font metrics, line spacing, and
window chrome, then reports only rows and columns to the TUI. An API-created
PTY can instead retain its independent 80×24 default even when its output is
shown inside a much larger application window.

Opening the initial symmetric Meld setup at 80×24 caused prompt-toolkit to show
its own `Window too small...` fallback. The string does not originate in this
repository. The initial layout stacks a seven-row operation-shape frame, two
source frames with two-row reach controls, a result frame with a three-row new
name section, frame borders, header/separator rows, Apply, and a footer. Its
fixed vertical requirements exceed 24 rows before useful tree space is
available. Running the same setup after `stty cols 140 rows 50` rendered and
worked normally. This identifies insufficient PTY rows as the failure boundary,
not a Meld endpoint-selection failure. Width can still affect wrapping and
readability, but 24 rows are independently insufficient.

No compact 24-row layout or automatic resize was introduced in response. For
the current API PTY, explicitly increasing the reported character grid is the
appropriate operational workaround.

## Other black-box findings and changes

### Close shortcut

Compare displayed `Q close`, but the uppercase `Q` key did not close it;
lowercase `q` did. Most terminal screens had independently registered only the
lowercase form, while endpoint setup had already registered both.

The close shortcut now uses one shared case-insensitive binding across every
existing `q`-to-close call site. Both `q` and `Q` close from the same read-only
surfaces. Each caller's existing focus filter is retained, so neither key is
intercepted as a close command while a writable input owns focus.

### Final Responses summary

After responses had been incorporated and the revised proposal had no remaining
review items, final Review and Apply displayed `RESPONSES · 0/0 ANSWERED` and
`No staged issue responses yet.`. That was mathematically harmless but described
the ready current proposal as if response work had never occurred.

A ready `APPLY`/`APPLY AS IS` proposal with zero reviewable items now says
`No open issue responses remain in the current proposal.` and omits the `0/0`
line. It deliberately does not claim a historical incorporated-response count,
because the generic workbench view does not retain one.

### Verification after the changes

- focused primitive, Compare, Resolution, and endpoint tests: 146 passed;
- broader tests for all affected terminal screens: 637 passed;
- Ruff and `git diff --check`: passed; and
- the complete suite reached 2,625 passes, but separate dirty-worktree state
  left 38 failures and 39 errors, mostly because the Task 2 discovery corpus no
  longer matched its frozen calibration lock. Two other unrelated failures were
  an Atomize screen-capture mismatch and a merge error-message mismatch.

## Second-run method

Use a small black-box PTY driver rather than manually advancing one interactive
exec session. It should still obey the same evidence boundary, but should:

1. open the CLI with `pty.openpty()`;
2. set the exact character grid through `TIOCSWINSZ` before launch;
3. timestamp and retain each raw terminal frame and each key sent;
4. send literal sequences such as Up `ESC [ A`, Down `ESC [ B`, Left
   `ESC [ D`, Right `ESC [ C`, Enter `CR`, Tab `HT`, Shift-Tab `ESC [ Z`,
   Escape `ESC`, and both `q` and `Q`;
5. normalize terminal control sequences only for the readable copy while
   retaining the raw capture for reproduction; and
6. stop on an ambiguous screen or blocker instead of consulting source or
   answer material.

The agreed standard viewport for the repeated Task 2 run is **140 columns × 50
rows**. Configure it before opening the first interactive `mem` screen:

```text
stty cols 140 rows 50
stty size
```

The verification output must be `50 140` because `stty size` prints rows before
columns. Record that output at the start of the trace. Treat 140×50 as the
conservative Full HD terminal reference for the repeat, not as a pixel
resolution and not as a claim about the TUI's minimum supported size.

Run the setup-size check as a two-axis matrix before the semantic exercise:

| PTY columns × rows | Purpose |
|---|---|
| 80×24 | Reproduce the original fallback |
| 80×50 | Isolate whether additional rows are sufficient |
| 140×24 | Confirm that width alone cannot satisfy the vertical minimum |
| 140×50 | Known working control |

The size matrix is a short layout diagnostic only. After it, restart from a
fresh 140×50 PTY and perform the complete semantic exercise there so the main
trace has one stable viewport from beginning to end.

If the next run is intended to test the actual 1920×1080 graphical terminal
instead, use a real terminal-emulator window and begin by recording `stty size`.
The pixel resolution alone is not a usable TUI size: the measured rows and
columns after font and viewport layout are the controlling values.

## Second-run execution record

The first alternative attempted was Computer Use against the running macOS
Terminal application. The Computer Use environment rejected control of
`com.apple.Terminal` for safety reasons before any Terminal action occurred.
The run therefore used the recorded black-box PTY alternative.

The outer 140×50 PTY launched a nested shell through macOS `script -r -k -F`.
Unlike the first run, `script` recorded input, output, and timing in its native
replayable format. The raw trace from this run is:

```text
/tmp/memcommit-task2-repeat.SjMxUU/session.typescript
size: 137 KiB
sha256: 6d0a304552c4fdf40f4e18086bccb3f09cc3bfcd07a19a93171bf4d45287a6de
```

The path is a machine-local temporary artifact, while this section is the
durable semantic index. Do not treat the raw terminal-control stream as a
human-readable document without replaying or normalizing it.

### Exact interaction index

1. `stty size` printed `50 140`.
2. `mem help` opened the interactive inventory.
3. `Shift-Tab`, then `Right`, selected the A–Z view.
4. A rapid batch of 26 `Down` events behaved like held navigation and reached
   the final `update` entry. `Home`, three `PageDown` events, and one `Down`
   reached `merge`; six `Up` events then selected `init-study`.
5. `Enter` opened the four visible `init-study` forms. A second `Enter` emitted
   the Form 1 prefill but did not execute it in the nested shell, so the visibly
   disclosed `mem init-study` command was typed and submitted directly.
6. `Enter` accepted the generated name
   `study-20260809T225208Z-758d14bb`. Initialization reported 65 Contexts, 457
   participant Memories, 43 granted Contexts, and 625 granted Memories.
7. `mem contexts` exposed the Task 2 local and granted namespace.
8. `mem show task-2/description` failed because `show` interpreted the operand
   as a Memory selector in the current Task 1 Context. The visible error was
   followed by `mem switch task-2/description` and `mem show`, which displayed
   the one Task 2 description Memory.
9. `mem compare` opened an empty saved-session picker; `Enter` opened Add new
   Compare.
10. In endpoint A, two `Up` events moved from `task-2/description` to
    `task-2/advisor1`; `Enter` selected it, `Tab` entered Range, `Right` selected
    descendants, and `Tab` entered endpoint B.
11. In endpoint B, two `Down` events reached `task-2`, `Right` expanded it, two
    more `Down` events reached `task-2/advisor2`, and `Enter` selected it.
    `Tab`, `Right`, `Tab` selected descendant reach and moved to Apply.
12. `Enter` started Compare. The provider relation analysis ran for about 215
    seconds without a layout fallback.
13. Compare then failed at its save boundary with
    `Compare error: The active Profile no longer matches the granted artifact binding.`
14. `exit` closed the nested shell and flushed the trace. `script` returned a
    nonzero status because the final semantic command had failed.

The repeated Task 2 exercise stopped at that error, as required by the
black-box boundary. No source or answer material was inspected and no retry,
Profile reset, Meld, or result materialization was attempted. A concurrent
global Profile change is a plausible external-state explanation, especially
when another Study workflow is active, but this remains an inference rather
than a source-level diagnosis.

## Third-run execution record

The third run repeated Task 2 after the Study action input recorder had been
updated. The preflight command `pytest -q tests/test_study_action_log.py`
reported `4 passed`. The exercise then used only `mem help`, the Task 2
description displayed by `mem show`, and subsequent terminal-disclosed
instructions and reports. No fixture source, expected result, or answer
material was inspected.

Every interactive command was launched through macOS `script -q -r -k -F`
after `stty rows 50 cols 140`. Unlike the second run's single nested shell,
this run retained one raw replayable file per command under:

```text
/tmp/memcommit-task2-third.DyHScw/
```

The two material semantic traces are:

```text
11-compare.typescript
sha256: e96cc0ae9af643e41fa2f4f03966d5f02dcea678227b8cdb940410d670cc11bc7

13-meld.typescript
sha256: 445ffed60ebb023cf0245d2cdfb52b9b891a02fe1e150be2f4cb90845b2a7312
```

This run did not repeat the four-size layout matrix and did not record a
standalone `stty size` line. The outer launcher nevertheless set 140 columns
and 50 rows before every recorded interactive process. Study action output
from a later 140x50 status invocation also reported
`terminal_columns=140` and `terminal_rows=50`, although another concurrent
Study had become active by that later inspection.

### Exact interaction index

1. `mem help` opened the inventory. `Tab`, `Right`, and `Down` selected the
   A-Z list; 15 `Up` events reached `merge`, and six more selected
   `init-study`. Two `Enter` events exposed the Form 1 prefill.
2. `mem init-study` opened the name editor. `Enter` accepted
   `study-20260809T234917Z-26ac4aab`, creating and selecting its participant
   and granted-memory Profile pair.
3. `mem list` showed the initial Task 1 Context. `mem switch` then moved two
   rows down to `task-2`, `Right` expanded it, and `Down`, `Enter` selected
   `task-2/description`. `mem show` displayed the single Task 2 description.
4. A second `mem help` visit selected A-Z `meld`. `Enter` expanded Meld,
   three `Down` events reached Form 4, and `Enter` disclosed
   `mem meld [context1] [context2] --to [result_context]`.
5. The Context picker expanded `task-2/participant` and revealed
   `task-2/participant/proposal-workspace`. `mem show` confirmed zero direct
   Memories plus embedded `task-2/advisor1`, embedded `task-2/advisor2`, and
   the query-only proposal-submission guideline.
6. The first `mem meld task-2/advisor1 task-2/advisor2` invocation stopped at
   its normal prerequisite guard and displayed the exact ordered commands
   needed to create its saved Compare basis.
7. The disclosed `mem switch task-2/advisor1` and
   `mem compare --to task-2/advisor2` commands were run directly. Compare
   analyzed for about 195 seconds and successfully saved analysis
   `cb04ffdf`: 300 Memories, 111 relations, and five potential conflicts.
   Lowercase `q` closed the Compare viewer successfully.
8. The disclosed `mem switch task-2/participant/proposal-workspace` command
   restored the result target. Repeating
   `mem meld task-2/advisor1 task-2/advisor2` reused `cb04ffdf` and opened the
   140x50 Meld workbench without a small-window fallback.
9. `Tab`, `Down`, `Enter` opened the first required conflict. `Tab` traversal
   entered Responses. `Down`, `Enter` selected `Conditional third` for the
   opening-length conflict.
10. For each remaining required conflict, `Tab`, `Down`, `Enter` opened the
    next item. `Tab` entered Responses; two `Down` events and `Enter` opened
    the inline Response field. The saved responses were:

    - Navigation structure: use three short descriptive subheadings while
      connecting their sections with explicit paragraph transitions.
    - Em-dash policy: avoid em dashes in this proposal because of the known
      repetition risk, while retaining selective use only as broader guidance
      outside this submission.
    - Participant target: use one primary exact target, adding justified
      minimum and maximum contingency cases when confirmations can change.
    - Budget placement: keep decision-relevant totals, categories, links, and
      a one-line basis in prose while placing detailed arithmetic in a clearly
      referenced compact table or appendix.

11. Three `Tab` events focused To Do. `Enter` opened the final review;
    `Shift-Tab`, `Enter` confirmed `INCORPORATE RESPONSES`. The provider Meld
    turn ran for about 454 seconds and returned with no open Items and `APPLY`
    available.
12. `Shift-Tab`, `Enter` opened the exact Apply review. A second
    `Shift-Tab`, `Enter` applied the reviewed proposal. The terminal reported
    `APPLIED · Round: 2`, source coverage `300/300`, relation coverage
    `111/111`, 208 final Memories, 182 `PRESERVE`, 21 `COALESCE`, five
    `SYNTHESIZE`, and zero required or helpful open issues.

No `StudyActionError` or unhandled event-loop exception occurred during the
run. In particular, the focus moves, Enter events, terminal redraws, and long
Meld session did not reproduce the earlier invalid Study action key failure.

### Post-run concurrent Profile observation

The successful Meld process itself printed the exact Task 2 result target and
`APPLIED` accounting. Immediately afterward, however, a separate `mem status`
invocation displayed another Study's Task 1 Context, and a later read-only
`mem profile current` displayed
`study-20260810T000728Z-54da735c` with a Task 3 current Context. This indicates
that another process changed the shared global active Profile after or near
the successful Task 2 apply. The run did not switch back, retry, or alter that
other Profile. Consequently, the final post-run action-log view belonged to
the other active Study and cannot be used as the Task 2 run's own ledger
verification; the raw Task 2 traces and the Meld process's final applied
receipt remain the evidence for this execution.

## Fourth-run Undo and no-selection attempt

This run tested two separate questions through terminal-visible behavior only:
whether the applied Task 2 Meld could be undone, and whether a fresh Meld could
advance while all conflict choices and free-form responses remained unset. It
used the same 140x50 recorded PTY boundary and did not inspect implementation
source, fixtures, expected results, or answer material.

The replayable command traces are under:

```text
/tmp/memcommit-task2-no-selection.SlZALg/
```

The most relevant trace digests are:

```text
05-undo.typescript
sha256: 552ba95961675c4caacfbd676272f9ebad12610906d0589599e94e74ebd64d50

07-meld-no-selection.typescript
sha256: 42eb46c3f19cf43b98781e9723ba403572782341f7b8a1b7e6e4c072187b545c

08-meld-sessions.typescript
sha256: 1d1e59d0fa4e6ab623a5a67b6ae609527f821fa15a175a44b6ae0db65a34e1c0

09-profile-after-blocker.typescript
sha256: 6f5a89ed97369ca98f482b5f317a6c58ad91f0477e18c5f7cee0f7369d04926a
```

### Exact interaction index

1. `mem help` was navigated to the Profile entry. Its displayed concise form
   was used to run
   `mem profile study-20260809T234917Z-26ac4aab`, restoring the Profile from
   the successful third run. The command reported the Task 2 result Context
   as current and 665 owned Memories in the Profile.
2. A second `mem help` visit selected A-Z `undo`. `Enter` exposed the exact
   Form 1 command `mem undo`; lowercase `q` closed Help without prefilling or
   executing it.
3. Immediately before the mutation, read-only `mem profile current` confirmed
   `study-20260809T234917Z-26ac4aab`, 665 owned Memories, and current Context
   `task-2/participant/proposal-workspace`.
4. `mem undo` succeeded without an additional confirmation surface. Its
   receipt identified the undone command as
   `mem meld task-2/advisor1 task-2/advisor2 --to
   task-2/participant/proposal-workspace --accept`, with one affected Context
   and 208 affected Memories, all 208 removed.
5. Read-only `mem status` then reported the result Context at zero Memories,
   with a new Undo checkpoint following the earlier 208-result Meld
   checkpoint. The Undo portion of this experiment therefore succeeded.
6. `mem meld task-2/advisor1 task-2/advisor2` reopened Compare analysis
   `cb04ffdf` as `REUSED`, but it also restored the already reviewed Meld
   proposal. Three `Tab` events focused `TO DO`; `Enter` opened the review,
   which said `No open issue responses remain in the current proposal` and
   `OPEN REVIEWS · NONE`. Escape returned and lowercase `q` closed without
   applying. The printed saved state was `READY_TO_APPLY · Round: 2`, with the
   previous five conflict resolutions already incorporated. This route could
   not constitute a zero-selection test.
7. `mem meld --sessions` was opened to obtain a genuinely new operation. The
   launcher displayed `+ Add new Meld session` and `No saved sessions yet`.
   `Enter` opened setup. Literal arrow and Tab navigation selected symmetric
   mode, A `task-2/advisor1`, B `task-2/advisor2`, and existing result C
   `task-2/participant/proposal-workspace`, all at `THIS CONTEXT ONLY`.
8. `Tab` focused Apply and `Enter` attempted to open the fresh operation. It
   stopped before any conflict choices or responses were displayed, reporting:

   ```text
   Meld error: Meld requires a saved Compare analysis for 'task-2/advisor1' → 'task-2/advisor2'.
   Create the exact ordered Compare basis first:
     mem switch task-2/advisor1
     mem compare --to task-2/advisor2
     mem switch task-2/participant/proposal-workspace
   Then rerun:
     mem meld task-2/advisor1 task-2/advisor2
   ```

   This is retained as the exact historical observation. A later
   implementation change replaced that separate-command prerequisite:
   symmetric Meld now prepares and saves the exact ordered Compare basis from
   its frozen A/B receipt without switching the current Context. See
   `agent-records/docs/mem-meld-design-rationale.md`.

9. No disclosed prerequisite command was run. A final read-only
   `mem profile current` instead established that the shared global active
   Profile had changed to `study-20260810T000728Z-54da735c`, whose current
   Context was `task-3/local/healthcare-sharing-criteria-find`. This explains
   the new launcher's absent saved Task 2 session and Compare basis without
   requiring a source-level inference: the new setup process was operating in
   the other Profile.

The run stopped at that external-state boundary without retrying, changing the
Profile again, recreating Compare, selecting a conflict response, or applying
anything. Consequently, the Undo behavior is confirmed, and direct Meld
reopening is confirmed to retain prior responses, but this run does **not**
answer whether a genuinely fresh Meld permits materialization with zero
responses selected.

## Fifth-run two-action checkpoint Revert

This run tested the terminal-visible distinction between Context branching,
single-command Undo, and restoration to an older checkpoint. It created two
disposable applied operations in the empty Task 2 result Context, then used the
interactive Revert screen to restore the checkpoint immediately before both
operations. No implementation source, fixture, expected result, or answer
material was inspected.

All commands used 140x50 PTYs recorded under:

```text
/tmp/memcommit-task2-revert-two.uWv9z9/
```

The central traces are:

```text
05-add-one.typescript
sha256: 7432e3c7162f557c31062846113c2aad7c599cf2312272daf651bd861fffe620

06-add-two.typescript
sha256: 48ecd79b51158041b896d665adf9781c0c4243825147734004749d7ca036d880

08-revert-picker.typescript
sha256: 055adff961f17d997069a4c719bc8077b56f41999db7fc38a24ef6cd69c099ba

09-status-after-revert.typescript
sha256: 57b039aad3b7807912cc8dc9bb5bf213aacbb506ffa877b677981ee26f495667
```

### Observed command contract

`mem help` defined a CHECKPOINT as a recoverable history boundary created for
each applied operation and recorded per affected Context. It also exposed the
following distinct contracts:

- `mem branch` copies a local Source/current Context to an exact fresh Context
  name; `mem checkout -b` is its alias. It does not mean “move to an older
  state.”
- `mem undo` reverses only the most recent recorded Context command.
- `mem revert` opens the checkpoint picker. `mem revert [checkpoint]` restores
  an exact checkpoint and discards newer active checkpoints, while adding
  `--keep` preserves the newer checkpoints.

The displayed Add Form 1 was `mem add "[memory]"`. The displayed Revert forms
were the interactive picker, exact selector, exact selector with `--keep`, and
semantic description lookup.

### Exact interaction and result

1. The original Task 2 Profile
   `study-20260809T234917Z-26ac4aab` was selected. Preflight
   `mem profile current` and `mem status` showed
   `task-2/participant/proposal-workspace` with zero Memories and two existing
   checkpoints: Undo `5e358709`, then Meld `a9d313e5`.
2. Two separate applied operations were executed:

   ```text
   mem add "[revert-test-1] temporary checkpoint marker"
   mem add "[revert-test-2] temporary checkpoint marker"
   ```

   They created Memories `a9267171` and `c375b26f`. Status then reported two
   Memories and four checkpoints, ordered Add `09610343`, Add `c09b5a83`, Undo
   `5e358709`, Meld `a9d313e5`.
3. `mem revert` opened the new Revert screen with Items focused on the latest
   Add checkpoint. Two literal `Down` events moved the cursor to the earlier
   Undo checkpoint `5e358709`; `Enter` restored it.
4. Revert exited successfully and explicitly reported both temporary Memories
   removed. It also printed an exact recovery checkpoint, `e7e3e26a`, for
   undoing this Revert.
5. Final `mem status` showed zero Memories and three active checkpoints:
   recovery Revert `e7e3e26a`, restored Undo `5e358709`, and Meld `a9d313e5`.
   The two newer Add checkpoints were no longer in the active list, matching
   default Revert behavior. The pre-Revert state nevertheless remained
   recoverable through `e7e3e26a`.
6. Final `mem profile current` still showed the intended Task 2 Profile and
   result Context, with its owned-Memory total restored to the pre-test value.

The practical result is that moving two operations backward is implemented as
one exact checkpoint Revert, not two Undo calls and not a Context branch. The
default route shortens the active history after the selected checkpoint but
creates a dedicated recovery checkpoint; `--keep` is the explicit alternative
when the newer checkpoints must remain visible.

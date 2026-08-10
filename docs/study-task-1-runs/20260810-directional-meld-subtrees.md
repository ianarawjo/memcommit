# Study Task 1 directional Meld subtree run

## Scope and evidence boundary

This is the second fresh Task 1 terminal run and the first one to exercise a
Directional Meld whose incoming A and authoritative B both include their
lexical descendants. The task-solving phase used only `mem help`, command help,
the Task description, readable Context names, and terminal-rendered state. It
did not inspect fixtures, an answer key, or solution material.

The run used a dirty worktree at the repository root on 2026-08-10. A screen
PTY and its attached terminal were fixed at 120 columns by 40 rows before the
successful interactive launch.

## Fresh Study Profile and task

The actual initialization command was:

```text
mem init-study study-20260810T010815Z-meld-a-b
```

It created the participant Profile
`study-20260810T010815Z-meld-a-b` and the paired authority Profile
`study-20260810T010815Z-meld-a-b-granted-memory`. The current Context was
`task-1/participant/construction-updates`.

The visible Task description was read with:

```text
mem show --context task-1/description
```

It asked the participant to use verified construction updates to update every
affected part of the campus wiki and contribute the completed update. A
readable `mem contexts` listing showed the incoming construction subtree and
the granted writable `task-1/campus-wiki` subtree.

## Literal setup actions

`mem meld` first opened the saved-session launcher. The successful fresh setup
used these actual inputs, in order:

1. `N` opened New Meld;
2. Right selected `DIRECTIONAL · A → B`;
3. Down entered A's tree;
4. Down five times moved from `practice` to
   `task-1/participant/construction-updates`;
5. Enter selected A;
6. Tab moved to A Range, then Right selected `INCLUDE DESCENDANTS`;
7. Tab moved to B's tree;
8. Down selected `task-1`, Right expanded it, and Down selected
   `task-1/campus-wiki`;
9. Enter selected B;
10. Tab moved to B Range, then Right selected `INCLUDE DESCENDANTS`;
11. Tab moved to Apply; and
12. Enter submitted the setup.

The action ledger later represented the control keys as `right`, `down`,
`c-m` (Enter), and `c-i` (Tab), including the grouped `down × 5` event. The
execution receipt printed:

```text
SCOPE · A SELECTED + ALL DESCENDANTS · B SELECTED + ALL DESCENDANTS
```

An earlier launch used to stabilize and resize the attached terminal was
cancelled without creating a session. It changed no Context.

## Provider turn and result

The setup did not hit a semantic preflight limit. The Study action ledger for
command `c7446a4f` recorded:

```text
PROVIDER_TURN_STARTED
  provider=codex_chatgpt · operation=meld_contexts
  input_characters=131612 · has_schema=True

PROVIDER_TURN_COMPLETED
  elapsed_seconds=179.61217074999877
  output_characters=22794
```

The returned session was immediately ready to apply:

```text
READY_TO_APPLY · DIRECTIONAL MODE · 6 RELATIONS
0 required + 6 helpful ISSUES · 6 CHANGES
75/375 SOURCE COVERAGE
```

All six issues were optional `SCOPED` questions. The default proposal preserved
the standing baseline Memories and synthesized one independently revisable
construction-period overlay for each affected target owner.

## Review and application actions

From the report, Tab moved to Items. Down seven times traversed the six helpful
issues and reached To Do. Enter opened `REVIEW AND APPLY`.

The run also intentionally exercised the report controls. Escape and Backspace
returned to the complete report, End opened the last issue, and Page Down from
the report also reached the last issue rather than revealing proposal text as a
free-scrolling page. These actions changed no selection.

As in the first Update run, pressing Enter immediately on the initial
confirmation view returned without applying. The successful final path was:

1. return to To Do;
2. Enter to present `REVIEW AND APPLY`;
3. Down to focus the inner `APPLY` card; and
4. Enter to approve the exact current proposal.

The ledger recorded a distinct `APPROVAL_PRESENTED`, Down key,
`APPROVAL_ACCEPTED`, and final Enter. Command `c7446a4f` finished successfully
after 461.462 seconds including setup, review, and provider time.

## Applied owner routing

The terminal printed `State: APPLIED · Round: 1` and six additions with these
exact owners:

| Proposal | Owner Context |
|---|---|
| Building access overlay | `task-1/campus-wiki/building-access` |
| Event relocation overlay | `task-1/campus-wiki/event-relocations` |
| Temporary parking overlay | `task-1/campus-wiki/temporary-parking` |
| Shop and amenity overlay | `task-1/campus-wiki/shop-updates` |
| Facility operations overlay | `task-1/campus-wiki/facility-updates` |
| Route closure overlay | `task-1/campus-wiki/route-changes` |

Each child Context then reported 51 direct Memories, consistent with one new
overlay added to each 50-Memory baseline owner. The participant Source remained
unchanged. Re-running the same public directional route rendered the saved
`APPLIED` receipt without a provider call or second application.

## Display bug found during reproduction

The first saved-session launcher correctly showed the session as `APPLIED`, but
its `Public route hint` displayed A's `--left-descendants` and omitted B's
`--right-descendants`. This was a display/reproduction bug: the stored frame,
execution receipt, provider input, and six owner-routed writes all retained B's
descendant scope.

The directional route builders in `memcommit.commands.meld` and
`memcommit.commands.meld_sessions` were updated to retain the B flag. A focused
catalog regression now requires this complete route:

```text
mem meld task-1/participant/construction-updates \
  --left-descendants \
  --into task-1/campus-wiki \
  --right-descendants
```

The saved-session launcher was reopened after the fix and visibly displayed
`[6] --right-descendants`. `tests/test_meld_sessions.py` passed all 9 tests and
Ruff passed on the affected files.

## Captures

The Task 3 capture convention was reused: nine 1120×760 PNGs and matching text
files, plus a 3×3 contact sheet. They cover the description, literal key trace,
applied overview, optional issues, all six owner routes, post-apply owner
counts, the reproducible public route, and the content-free Study action-ledger
summary.

The capture set is under:

```text
outputs/study-task-1-directional-meld-screens/
```

`render_captures.py` regenerates the images from the active saved run's public
CLI state and fails if the expected Study Profile or six proposals are absent.

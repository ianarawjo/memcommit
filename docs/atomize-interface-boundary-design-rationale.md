# Atomize interface boundary design rationale

## Problem

Atomize's analysis and Apply semantics already had typed application/runtime
entry points, but the saved-session terminal screen still lived in
`memcommit.commands.atomize_workbench_shell`. The command module also assembled
the workbench destination editor and rendered Apply receipts. This made the CLI
the practical owner of a TUI that should be reusable by any terminal adapter,
and an interface module could not import the screen without depending outward
on `commands`.

## Selected boundary

The dependency direction is now:

```text
atomize domain/application/runtime
              ↑
interfaces/tui/workbenches/{review,result,resolution}
              ↑
interfaces/tui/operations/atomize/{screen,adapter}
              ↑
commands/atomize and commands/impact
```

- `interfaces/tui/operations/atomize/screen.py` owns the saved workbench's
  prompt-toolkit composition and operation-specific projection.
- `interfaces/tui/operations/atomize/adapter.py` converts a saved analysis,
  workbench, and `MemoryStore` orientation into that screen. It may save a
  draft through the supplied Store method, but it does not create analyses,
  call a provider, apply Memories, or bypass the typed application boundary.
- `interfaces/tui/workbenches/result` owns the shared read-only Result viewer
  used by Atomize. `interfaces/tui/workbenches/review` owns the small shared
  response label and normal-cancellation type.
- `interfaces/cli/atomize.py` owns plain impact and Apply-result rendering.
  The command still owns option parsing and orchestration, then delegates
  presentation.

The former `commands.atomize_workbench_shell`,
`commands.result_workbench_shell`, and `commands.atomize_render` modules remain
thin identity-preserving import facades. New implementation code and tests use
the interface-owned paths. The facades contain no layout, key binding,
rendering, provider, Store, or application behavior.

## Invariants

1. Interface-owned Atomize and Result modules import no `memcommit.commands`
   modules.
2. Moving the screen does not change saved analysis/workbench schemas,
   application receipts, checkpoints, Save As behavior, focus topology,
   keyboard actions, or non-TTY snapshots.
3. The adapter never treats screen completion as permission to mutate a
   Context. Apply still returns an operation action to `commands.atomize`,
   which invokes the typed application/runtime use case.
4. The Result viewer remains read-only and operation-neutral. Atomize owns only
   its projection into the common Result model.
5. Existing imports keep object identity through thin facades, so the move does
   not create two controller classes or two copies of mutable state.

## Alternatives considered

Keeping the implementation under `commands` and adding another wrapper under
`interfaces` would preserve imports but invert the intended dependency. Moving
all Atomize Grounding dialogue and analysis orchestration in the same change
would make functional parity harder to establish and mix semantic policy with
the terminal boundary. The selected slice moves the complete saved-workbench
presentation first; Grounding command/application extraction remains a
separate operation slice.

## Verification

The boundary tests parse every new interface-owned module and reject imports
from `memcommit.commands`. They also prove the old paths re-export the exact
same function objects. Atomize workbench, Result workbench, impact, Save As,
Undo/Redo, and application-boundary suites exercise snapshot, interactive,
application, failure, and recovery behavior. The ordered 180×52 color replay
under `docs/screenshots/atomize-apply-boundaries-20260815/` executes the new
screen path directly and retains the established eight-step review, Apply,
verification, compensation, late-success, recovery, and race evidence.

# Atomize console presentation ownership

## Problem

Atomize's analysis and Apply semantics have typed application/runtime entry
points, while every current presentation consumer is a console command. The
plain receipt, Grounding transcript, and saved-session workbench had been split
between `adapters.interfaces.cli`, `adapters.interfaces.tui.operations`, and
thin modules under `commands.atomize`. That split obscured the single console
owner and required compatibility facades even though there was only one live
implementation of each presentation.

## Selected boundary

The dependency direction is now:

```text
atomize domain/application/runtime
              ↑
interfaces/tui/workbenches/{review,result,resolution}
              ↑
commands/atomize/{render,grounding,workbench}
              ↑
commands/atomize/command and commands/impact/command
```

- `commands/atomize/workbench/screen.py` owns the saved workbench's
  prompt-toolkit composition and operation-specific projection.
- `commands/atomize/workbench/adapter.py` converts a saved analysis, workbench,
  and `MemoryStore` orientation into that screen. It may save a draft through
  the supplied Store method, but it does not create analyses, call a provider,
  apply Memories, or bypass the typed application boundary.
- `interfaces/tui/workbenches/result` owns the shared read-only Result viewer
  used by Atomize. `interfaces/tui/workbenches/review` and `resolution` own the
  operation-neutral response and session mechanics.
- `commands/atomize/render.py` owns plain impact and Apply-result rendering,
  and `commands/atomize/grounding.py` owns the provider-free Grounding
  transcript. The command owns option parsing and orchestration, then
  delegates presentation.

`impact atomize` imports the Atomize workbench screen from its operation owner.
That reuse does not make the screen operation-neutral: Impact is presenting a
saved Atomize analysis and its Atomize-specific findings. Shared Result,
Review, and Resolution mechanics remain under `interfaces/tui/workbenches`.

The former Atomize-specific interface paths and
`commands/atomize/workbench_shell.py` were removed rather than retained as
facades. Function names, screen behavior, and persisted models remain
unchanged, but callers must import the one command-owned implementation.

## Invariants

1. Atomize workbench modules do not reach through unrelated command packages;
   operation-neutral workbench mechanics remain shared interface modules.
2. Moving the presenters does not change saved analysis/workbench schemas,
   application receipts, checkpoints, Save As behavior, focus topology,
   keyboard actions, or non-TTY snapshots.
3. The adapter never treats screen completion as permission to mutate a
   Context. Apply returns an operation action to `commands.atomize`, which
   invokes the typed application/runtime use case.
4. The Result viewer remains read-only and operation-neutral. Atomize owns only
   its projection into the common Result model.
5. There is one implementation path for each Atomize presenter and no
   Atomize-specific compatibility facade that could drift from it.

## Alternatives considered

Keeping `interfaces/cli/atomize` and `interfaces/tui/operations/atomize` as
canonical owners would preserve the prior import direction, but every live
consumer is a console command and the extra boundary required Atomize-specific
facades. Moving the workbench to an operation-neutral shared package was also
rejected: its finding projection, destination rules, and actions remain
Atomize-specific. The selected move co-locates presentation only; Grounding
semantics, provider work, Store transactions, and Apply policy remain in the
application/runtime boundary.

## Verification

Boundary tests prove that the removed paths are absent, the Atomize and Impact
commands import the command-owned presenters, and the workbench does not reach
through unrelated commands. Atomize workbench, receipt, Grounding, Impact, Save
As, Undo/Redo, and application-boundary suites exercise snapshot, interactive,
application, failure, and recovery behavior. The existing ordered 180×52
replay under
`agent-records/docs/screenshots/atomize-apply-boundaries-20260815/` imports the
new screen path; no visible interaction changed, so its captured frames remain
valid.

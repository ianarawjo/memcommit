# Command package layout design rationale

## Problem

Before the command-package layout pass, `memcommit.commands` contained 154
Python files and no real child package. A command with several adapters encoded
membership in repeated filename prefixes such as `atomize_*`, `ground_*`, and
`meld_*`. A command with one file occupied the same flat namespace, so adding a
second file later also required changing its physical shape. File-browser
navigation could not answer which files composed one CLI entry without first
knowing every naming convention.

## Decision

Every Python command entry has one package, including entries that currently
need only one implementation file. Its executable adapter normally lives in
`commands/<entry>/command.py`; an adapter with independently meaningful CLI
and workflow responsibilities may instead use a nested
`commands/<entry>/command/` package. The entry's `__init__.py` publishes only
the CLI surface used by composition (`cmd`, `app`, or the two write-protection
apps). That surface loads lazily: importing a sibling such as
`find.chat_shell` must not initialize `find.command` and create a cycle back
through operation code.
Files used by one entry live beside that command and drop the repeated prefix:

```text
commands/atomize/
  __init__.py
  command.py
  render.py
  sessions.py
  workbench_shell.py
```

Command-layer mechanics used by more than one entry live under the sibling
`adapters/console/coordination/` package. This is not a general utility directory: a
module belongs there only when its console-adapter mechanics genuinely have
multiple command consumers. Keeping it outside `commands/` makes that tree's
physical invariant exact: every first-level child is an actual command entry
package. Application policy remains under `operations/`; operation-owned
console presentation and interactive setup live beside their command. Shared
terminal foundations and Viewer/Workbench compositions live in the sibling
`adapters/console/terminal/` core and component tree. Other neutral concepts
keep their existing owners.

The exact baseline classification is authored mechanically by
`scripts/render_command_package_layout.py` and rendered in
`agent-records/docs/command-package-layout-plan.json` and
`agent-records/docs/command-package-layout-plan.md`. The baseline contains 153 non-package
modules. Its active mappings comprise 63 entry packages, 43 entry-owned support
modules, and 42 shared command-support or terminal-component modules;
Atomize Grounding, `shell_init`, the unpublished named-Ground/session-picker
adapters, and Meld's superseded target picker remain only in the
retired-baseline inventory after their active responsibilities moved to their
current operation or shared component owners.

On 2026-08-27 the complete, already packaged command tree moved unchanged from
`memcommit.commands` to `memcommit.adapters.console.commands`. Its dominant
responsibility is translating console invocations into application calls and
presenting their results through Typer, prompt-toolkit, and terminal rendering;
it is therefore an implementation of the console adapter rather than a peer
architectural layer. This is deliberately a physical staging move. Command-local
application policy that may later belong under `memcommit.application` is not
split during this relocation.

On 2026-08-28 the multi-command `shared/` package moved one level upward from
`adapters/console/commands/shared/` to `adapters/console/coordination/`. The earlier
placement correctly identified these modules as console adapters but made
`commands/` describe both command entries and cross-command infrastructure.
The sibling placement preserves the same adapter layer and dependency meaning
while giving the command tree one navigational grammar. No compatibility
package remains at the former internal path.

On 2026-08-30 the two historically inverted Find package names were aligned
with their public commands. `commands/find_duplicates` now owns the
provider-free exact-Duplicate route, and `commands/find_redundancies` owns the
semantic Redundancy route; `find_ambiguities` and `find_conflicts` were already
named after their public entries. The relocation changes no CLI spelling or
analysis behavior and retains no alias package for the former internal names.

Reference's interactive setup likewise lives under
`adapters/console/commands/reference/workbench/`. It selects the Reference
unit, Source, Context scope, and local Target and freezes the reviewed exact
command, so it is command-owned console composition rather than a generic TUI
operation. The move preserves its model, Store-port composition, screen, and
application-plan boundary unchanged; shared selectors and focus mechanics
remain with their existing neutral owners, and no compatibility facade remains
at the former internal path.

## Ground command adapter split

The later Ground-focused pass replaced its original command monolith with a
same-named package. After the unpublished JSON session prototype was retired,
`entrypoint.py` reduced from 52 parameters to the 12 physical-workspace and
draft inputs that still have product meaning. It constructs one frozen
`GroundCommandRequest`; `command.py` routes it, `create.py` owns the unsaved
conversation and draft-to-Ground transition, `edit.py` owns physical creation
and direct edits, `open.py` owns workspace/draft discovery and reopening,
`inspect.py` owns the unsaved entry view, and `apply.py` owns the approved
logical command primitive.

The former `workflow/session/`, `named_shell/`, legacy session picker, and
saved-session dialogue interpreter are deleted. The active dependency
direction runs from `command.py` toward those physical action modules, and
lower modules do not import the command router at runtime. The entrypoint must
never implement an Apply path or reproduce a freshness check: it constructs
the typed request and delegates once. Shared launcher orientation now lives in
the operation-neutral launcher component rather than a Ground legacy module,
because Atomize, Review, and Impact also consume it.

## Why single-file entries are packages

Keeping single-file entries flat would save one directory level today but
would preserve two navigation grammars: some commands would be files and
others directories. A reader would also have to re-learn the path when an
entry acquired setup, session, or workbench support. At this repository's
operation count, stable and symmetric lookup is more valuable than avoiding
one click. The package shape makes `commands/<entry>/` the invariant starting
point and keeps future growth local.

## Copy and Move command ownership

Copy and Move were later extracted from one combined console-interface module.
Each displayed Help operation now has its own `commands/copy` or
`commands/move` package containing its grammar, operation-specific setup,
application handoff, and receipt. Their common direct-Memory selection,
Target-gap placement, editable exact-command, operand, and placement-receipt
mechanics live in the sibling `adapters/console/coordination/memory_transfer`
package. A `commands/memory_transfer` package was rejected because it would
look like a third executable command, while `copy_and_move` would name current
consumers rather than the shared concept. The application transaction remains
under `application.operations.memory_transfer`.

## Compatibility boundary

Within the canonical console tree, every entry package continues to publish its
intended CLI object. For example, `memcommit.adapters.console.commands.add.cmd` and
`memcommit.adapters.console.commands.atomize.cmd` remain valid while internal code imports the
implementation-owning `.command` module directly.

Ground additionally preserves imports from its historical `.command` module
through the command and workflow package `__init__.py` facades. Helper
implementations are not copied: lookup returns the object from its canonical
action or `session/` owner. Tests that replace a workflow dependency patch
that owning module rather than relying on assignment to either compatibility
package to rewrite another module's globals.

The 89 former flat support-module paths cannot be represented by both a file
and the new package tree. They were initially served by a generated lazy alias
catalog, but that compatibility had no external consumer or continuing intent
and was removed on 2026-08-27. Repository-owned callers now import the
entry-owned or shared canonical module directly. The later outer relocation
also removes the complete `memcommit.commands` namespace; no compatibility
facade retains either its entry-package or flat support paths.

The Python entry package names intentionally retain the pre-existing module
stems in this path-only pass. Historical mismatches between a Python module
name and a displayed Help operation, such as semantic Search and literal Find,
are a separate naming decision rather than something inferred from a prefix
move.

## Verification

The layout check requires the console-owned `commands/__init__.py` to be the only Python file at
the command root, rejects a nested `commands/shared` package, verifies every
classified command target, shared-console target, and entry package, rejects
internal imports through all 153 historical command names, and proves
in an isolated interpreter that neither those names nor `memcommit.commands`
itself is restored. Package tests
also verify that all 63 `__init__.py` files expose only their declared CLI
surface.

## Alternatives rejected

- Grouping only commands with multiple files would retain two physical
  grammars and make later growth change a command's path.
- Grouping solely by textual prefix would incorrectly absorb independent
  commands such as the quality finders and would turn naming accidents into
  ownership claims.
- Keeping forwarding files at the flat command root would preserve the exact
  navigation problem this change addresses.
- Moving application or presentation code merely to make a command directory
  look complete would blur the already established `operations/` and
  `interfaces/` ownership boundaries.

## Non-goals and remaining boundary

The original package-layout pass did not split large command modules, rename
CLI operations, change command behavior, or claim that every current command
dependency was correctly directed. The later Ground split narrows only that
command's already visible adapter responsibilities; it does not move Ground
policy into the console layer or consolidate the blank and named TUI shells.
The pre-existing Search operation imports of command session and chat adapters
remain visible reverse dependencies for later semantic ownership work. The
layout makes those dependencies locatable; it does not silently resolve them.

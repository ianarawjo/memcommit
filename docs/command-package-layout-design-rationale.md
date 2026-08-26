# Command package layout design rationale

## Problem

After the root ownership relocation, `memcommit.commands` still contained 154
Python files and no real child package. A command with several adapters encoded
membership in repeated filename prefixes such as `atomize_*`, `ground_*`, and
`meld_*`. A command with one file occupied the same flat namespace, so adding a
second file later also required changing its physical shape. File-browser
navigation could not answer which files composed one CLI entry without first
knowing every naming convention.

## Decision

Every Python command entry has one package, including entries that currently
need only one implementation file. Its executable adapter lives in
`commands/<entry>/command.py`, and its `__init__.py` publishes only the CLI
surface used by composition (`cmd`, `app`, or the two write-protection apps).
That surface loads lazily: importing a sibling such as `find.chat_shell` must
not initialize `find.command` and create a cycle back through operation code.
Files used by one entry live beside that command and drop the repeated prefix:

```text
commands/atomize/
  __init__.py
  command.py
  grounding.py
  render.py
  sessions.py
  workbench_shell.py
```

Command-layer mechanics used by more than one entry live under
`commands/shared/`. This is not a general utility directory: a module belongs
there only when its command-adapter mechanics genuinely have multiple command
consumers. Application policy remains under `operations/`, presentation
ownership remains under `interfaces/`, and other neutral concepts keep their
existing owners.

The exact baseline classification is authored mechanically by
`scripts/render_command_package_layout.py` and rendered in
`docs/command-package-layout-plan.json` and
`docs/command-package-layout-plan.md`. The baseline contains 153 non-package
modules, classified into 64 entry packages, 48 entry-owned support modules,
and 41 shared command-support modules.

## Why single-file entries are packages

Keeping single-file entries flat would save one directory level today but
would preserve two navigation grammars: some commands would be files and
others directories. A reader would also have to re-learn the path when an
entry acquired setup, session, or workbench support. At this repository's
operation count, stable and symmetric lookup is more valuable than avoiding
one click. The package shape makes `commands/<entry>/` the invariant starting
point and keeps future growth local.

## Compatibility boundary

The former entry-module path now names the package and continues to publish its
intended CLI object. For example, `memcommit.commands.add.cmd` and
`memcommit.commands.atomize.cmd` remain valid while internal code imports the
implementation-owning `.command` module directly.

The 89 former flat support-module paths cannot be represented by both a file
and the new package tree. They are therefore recorded in one generated lazy
alias catalog, `memcommit.compatibility._legacy_command_alias_map`, and resolved
by the existing exact compatibility finder. Each historical support import
returns the canonical relocated module object without restoring a flat file or
eagerly importing all commands. The catalog preserves old imports; it does not
make arbitrary command-module helper attributes a public API.

The Python entry package names intentionally retain the pre-existing module
stems in this path-only pass. Historical mismatches between a Python module
name and a displayed Help operation, such as semantic Search and literal Find,
are a separate naming decision rather than something inferred from a prefix
move.

## Verification

The layout check requires `commands/__init__.py` to be the only Python file at
the command root, verifies every classified canonical target and entry package,
rejects internal imports through the 89 historical support names, and imports
each alias in isolated interpreters in both orders. Package tests also verify
that all 64 `__init__.py` files expose only their declared CLI surface.

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

This pass does not split large command modules, rename CLI operations, change
command behavior, or claim that every current command dependency is correctly
directed. In particular, the pre-existing Search operation imports of command
session and chat adapters remain visible reverse dependencies for later
semantic ownership work. The layout makes those dependencies locatable; it
does not silently resolve them.

# Profile console package design rationale

## Motivation and scope

The 1,461-line Profile command module combined CLI registration, inventory
projection and rendering, picker orchestration, ordinary Profile lifecycle,
Study-member Profile operations, Grants, and legacy Context migration. These
concerns change independently, while the application layer already owns the
underlying Profile lifecycle, Study, and Grant operations.

This change separates console responsibilities without changing command names,
arguments, output, interactive steps, application transactions, or authority.

## Ownership and dependencies

- `command.py` composes the root Typer app and registers commands in their
  existing order. The default callback and optional-name `use` entry point
  choose between non-interactive output, the selector, and direct selection.
- `lifecycle.py` handles ordinary create, rename, remove, import, and actual
  selection, including the existing Study leave/enter accounting.
- `study_profile.py` handles remove-study, rename-study, and archive-study.
  Its name describes operations on Study-member Profiles, rather than claiming
  ownership of all Study behavior.
- `grants.py` owns its Typer sub-app, Grant command handlers, and Grant output.
- `migration.py` owns legacy Context migration preview/Apply, frozen-Grant
  blocker checks, Profile and graph preconditions, and safe shell rendering.
- `inventory.py` loads Profile rows, projects Study membership, and supplies
  frozen data to list/current renderers.
- `presentation.py` renders inventories, lifecycle receipts, and picker status
  messages. Its membership-type import is type-checking-only, so rendering
  does not load inventories or create a runtime import cycle.
- `selector.py` builds picker entries, dispatches reviewed actions, and reloads
  the catalog after mutations. The existing `picker.py` retains screen and
  keyboard mechanics; `group.py` retains shorthand routing.
- `_support.py` contains only common CLI failure translation and terminal
  detection. It owns no operation behavior.

Root command registration references imported handlers rather than requiring
handler modules to import the root app. The optional-name `use` dispatch stays
at the root so lifecycle does not depend back on selector. Application imports
now name their narrow implementation owners. Shared result renderers avoid
coupling the selector to Study command handlers.

## Preserved contracts

- `profile.app` remains the lazy public entry point. Existing command ordering,
  hidden `ls` aliases, Grant aliases, options, and Profile-name shorthand remain.
- Picker mutations retain expected UID/generation checks and fresh catalog
  reloads. No reviewed action reuses the previous generation after mutation.
- Selection retains its existing post-change ledger failure receipt: ledger
  failure must not imply that the Profile selection was rolled back.
- Migration retains the exact frozen store root, Profile UID and graph digest
  checks, Grant blockers, and plan/apply sequencing.
- Membership validation, owned/granted inventory distinctions, display escaping,
  semantic colors, and deletion confirmations remain unchanged.

## Alternatives and limitations

A generic helpers module or a single large command-handler replacement would
retain mixed ownership. Conversely, one file per command would scatter closely
related receipts and workflows. Modules are grouped by responsibility instead.

This is a structural extraction, not a new application boundary. Migration
still orchestrates the existing store API in the console adapter. Study
membership projection still contains its existing validation checks; moving
those checks into application services is a separate behavioral design task.
No new interactive state is introduced and picker implementation is unchanged.

Tests that patched moved command-module globals now patch the module that
actually uses the dependency; no compatibility forwarding layer is introduced
for private test seams. Existing public CLI entry points remain stable.

## Verification

Validation uses `PYTHONPATH=src` because the current shell does not have the
project installed. Across focused and integration runs, 206 distinct tests
passed: 151 Profile/Context-portability/clean-import tests, 5 command-group
ownership tests, and 50 Grant/Study-ledger/package-import tests.

One additional package-import test fails:
`test_internal_standalone_modules_remain_importable_without_ground`.
The same failure was reproduced against an isolated export of pre-change HEAD
(`c83fc3bcc`): Distill imports Summarize, then legacy prewarming, Meld, Resolve,
Audit, and Check Conformance, which imports Ground. This pre-existing boundary
failure does not pass through the Profile console package and is not changed
by this extraction.

A before/after comparison verified identical output for 19 help routes,
including hidden aliases and all subcommands. AST comparison found 42 original
function/class definitions unchanged after removing registration decorators.
The remaining two list/current handlers delegate their original rendering
statements unchanged to presentation. Picker and alias-group implementations
are unchanged. Ruff import/undefined-name checks, task-scoped diff whitespace checks, and
the operation-evidence registry check pass.

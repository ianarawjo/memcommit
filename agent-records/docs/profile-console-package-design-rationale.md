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
  the catalog after mutations. The `picker/` package owns interactive selection
  and exact review; `group.py` retains shorthand routing.
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
The original console extraction left picker implementation unchanged. The
subsequent picker split below makes its existing state transitions explicit.

Tests that patched moved command-module globals now patch the module that
actually uses the dependency; no compatibility forwarding layer is introduced
for private test seams. Existing public CLI entry points remain stable.

## Original console extraction verification

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
statements unchanged to presentation. At that stage, picker and alias-group
implementations were unchanged. Ruff import/undefined-name checks, task-scoped diff whitespace checks, and
the operation-evidence registry check pass.


## Picker responsibility split (2026-09-06)

### Motivation and ownership

The remaining 1,099-line picker mixed display contracts, Study row validation,
reviewed command projections, rendering, input transitions, and deletion
callback orchestration. `choose_profile()` alone occupied 655 lines. Moving
functions without separating its mutable closure dictionaries would preserve
the main coupling: each key handler, visibility filter, and back path had to
agree on the combination of pending action, rename target, and create flags.

The replacement groups these responsibilities under `profile/picker/`:

- `model.py`: frozen Entry, Row, Action, and Refresh contracts.
- `rows.py`: validate a frozen input inventory once and construct its rows.
- `review.py`: exact action/command/effect projections, with no execution.
- `state.py`: shared flat cursor state plus one active browse, name-edit, or
  exact-review layer. An edit's row position refers only to the frozen catalog;
  executable actions retain the raw name, UID, and registry generation.
- `presentation.py`: rows, headers, footers, shared exact-name controls, and
  layout. Rendering consumes already validated rows and never rebuilds the
  inventory. Field controls validate generic single-line input; the state
  transition validates the exact Profile/Study name contract.
- `app.py`: `choose_profile()`, key bindings, focus synchronization, and the
  operation's callbacks to the existing background executor.
- `__init__.py`: lazy public `choose_profile` access. Internal callers and tests
  import types and helpers from their narrow owners; private test patch points
  are not re-exported as a parallel implementation.

The composition direction is app toward presentation/state and then frozen
models and pure row/review functions. No picker component loads the registry,
mutates Profile stores directly, or imports the selector. `selector.py` still
builds inventory inputs, calls application mutations with expected identity
and generation, and reloads the catalog after completion.

### Preserved invariants and tradeoffs

One typed `stage` replaces independent create, rename, and review dictionaries.
Back from a create/rename review restores the exact reviewed draft; back from
input returns to the list. The shared field buffer owns text while editing;
the state receives it on submission. Programmatic draft restoration must not
be mistaken for a user edit that clears the back-navigation receipt.

`FlatSelectionState` owns bounded cursor movement. Study headers remain real
keyboard rows, while CURRENT continues to mean the active Profile rather than
the cursor. `dispatch_tui_back` routes Escape one layer at a time. Writable
Backspace and existing explicit approval keys retain their meanings.

Create and rename still return frozen actions for synchronous selector
execution. Deletion still invokes the supplied callback through
`BackgroundExecutorTurn`, rejects additional interaction while busy, and
finishes before honoring Escape/Ctrl-C close requests. Busy and close flags
remain exclusively owned by the shared executor, not duplicated in picker
state. Success and error both return the reviewed visual position for the
existing selector refresh/error path.

The report foreground now references the shared `REPORT_HEX` value rather
than repeating its literal. Other existing styles, frame order, command
wording, and input steps are preserved by this structural change. This split
adds no interactive flow and changes no application authority boundary.

A generic helpers module and a file-per-key-handler split were rejected because
both leave state ownership scattered. Moving all mutations into the picker or
forcing deletion to return before completion would disturb the existing
selector and close-after-deletion contracts. This refactor-only commit retains
existing legacy Study input fields, validation, labels, and member-rename
behavior. Independent Study lifecycle changes in the primary working tree
remain separate, unstaged work.

### Picker split verification

In the primary checkout, this focused integration run passed 138 tests:

```sh
PYTHONPATH=src python -m pytest -q tests/test_profile*.py tests/test_clean_profile_import.py tests/test_command_group_ownership.py tests/test_context_operand_rollout.py::test_profile_picker_escapes_metadata_but_returns_raw_identity
```

The new state tests cover exact rename/create drafts, frozen UID/generation,
invalid-name rejection, active-Profile/Study removal blocks, and the surviving
visual row after refresh. Input tests cover review-back editing, ordinary
Backspace deletion, duplicate approval suppression, and Escape/Ctrl-C during
successful and failed deletion callbacks.

A headless prompt-toolkit differential check compared the task-entry picker
with the replacement on a 180-column by 52-row virtual canvas. Eight paths
(selection, create/back/edit, rename/back/edit, Study rename, Study removal/back,
Profile removal, invalid-name recovery, and current-Profile removal rejection)
produced 41 identical rendered states, including text, styles, and layout.
Returned action payloads also matched after excluding the independently
retired legacy Study flag. The historical shared-control import was normalized
to its current physical owner for this comparison. This was a renderer check,
not a PTY screenshot capture.

A clean-process import check confirmed model/row/state imports do not load
picker app/presentation and that the public `choose_profile` is the canonical
app function. Ruff checks, focused diff whitespace checks, and
`python scripts/verify_operation_evidence.py --check` pass. This existing note
is already registered under Profile; the split changes no route classification
or evidence-index membership.


Before committing, the focused refactor was also exported over its original
HEAD without the other working-tree changes. The same focused test command
passed **145 tests** there, including the retained legacy Study cases. This
commit preserves those compatibility fields and behaviors; the later Study
lifecycle retirement remains an independent working-tree diff. The primary
checkout's 138-test result above covers the combined working state.

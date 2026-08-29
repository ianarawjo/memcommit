# Blank Ground runtime responsibility design rationale

## Problem

The blank-Ground `runtime.py` owned 2,707 lines and kept its session state,
provider-backed drafting turn, Context candidate selection, and prompt-toolkit
interaction in one 2,509-line closure. Proposal validation and read-only text
rendering were already separated, but the live runtime still made unrelated
changes share one file and hid which state was process-local rather than
durable.

## Selected layout

The historical `ground.shell.runtime` import is preserved as a package with a
thin public facade and four responsibility directories:

- `session/` owns validated startup, the explicit mutable session state, and
  terminal result projection. Durable mutation remains behind the injected
  Apply callback.
- `grounding_drafting/` owns the background bridge for one blocking interpreter
  call and freezes ASK or PROPOSE output before it gains UI authority.
- `context_selection/` owns typed candidate rows plus pure ordering, cursor,
  and selection rules. Its choices remain process-local hints and do not create,
  load, bind, or mutate a Context.
- `terminal_interaction/` owns the prompt-toolkit Application, widget and key
  grammar, Ground-specific pane activity projection, and focus-ring movement
  while continuing to reuse shared terminal components.

`entry.py` is a thin stable import facade. `terminal_interaction/application.py`
composes the other owners with the existing prompt-toolkit interaction grammar.
The first extraction leaves tightly coupled widget construction and key
callbacks together rather than introducing a large dependency object solely to
reduce one implementation file's line count.

## Invariants

- Existing imports of `ground.shell.runtime` and `run_ground_shell` continue to
  resolve to identical public objects.
- Existing patchable prompt-toolkit test seams remain available from the
  historical runtime facade.
- A provider response cannot directly author the approved argv; proposal
  freezing and exact-command construction remain in `proposal.py`.
- A directly edited Goal must still be preserved exactly by the provider turn.
- Context selection remains separate from Ground creation and cannot introduce
  a hidden Context mutation.
- Apply remains reachable only through the explicit frozen-command approval
  path, and an uncertain Apply failure is not automatically retried.
- Closing the shell makes a late background interpreter result observationally
  inert.

## Alternatives and limitations

Splitting every pane, editor, key group, and controller into its own package
would name more mechanics but would obscure the initial four conceptual
responsibilities. Keeping one runtime module would minimize movement but retain
the closure-owned state and mixed change surface. The selected first step makes
the shared state and pure boundaries explicit while retaining the established
interaction grammar. Later extraction from `entry.py` should follow a proven
responsibility or reusable terminal component, not a file-size target alone.

This record documents package ownership only. It does not classify the Ground
operation route or replace the authored operation evidence ledger.

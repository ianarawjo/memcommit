# Role-based session endpoint setup

## Problem

The shared SessionPicker gave Compare, Update, Meld, and Sever a consistent
way to reopen saved work, but choosing **New** dropped into unrelated operand
flows. Compare and Update opened sequential full-screen Context pickers, Meld
first asked for a textual mode and then opened two or three different pickers,
and Sever alone showed all of its roles together.

Sequential prompts hide the operation shape while a person is choosing it.
In particular, Meld does not visibly explain that directional and symmetric
work have different authority and target contracts:

```text
DIRECTIONAL  INCOMING A → BASELINE B
SYMMETRIC    PEER A + PEER B → RESULT C
```

The setup UI should make that shape continuously visible and reuse the same
Context namespace interaction as `mem switch`, without turning the four
operations into one semantic command.

## Implemented presentation

One role-based setup shell stacks the operation's active inputs in data-flow
order. Each existing-Context input embeds an independent `ContextTreeState`
over one frozen catalog. New-name and existing-or-new result inputs use a
role-specific editor or target pane rather than pretending a name under
construction is an existing Context.

Meld adds a focused horizontal mode selector above those inputs:

```text
 NEW MELD

 MODE  ‹ DIRECTIONAL · A → B ›   ‹ SYMMETRIC · A + B → C ›

 A · INCOMING / PEER     [Context namespace tree]
 B · BASELINE / PEER     [Context namespace tree]
 C · RESULT              [eligible empty Context or new exact name]
```

Only the selected mode's contract is active. In directional mode the C pane is
absent and B is visibly both the authoritative baseline and the eventual
mutation/session target. In symmetric mode C is visible as the distinct result
and target-bound session owner. Labels may adapt with the mode, but stable A,
B, and C role identities keep selection state and tests independent of display
wording.

The other initial configurations are:

| Operation | Visible shape | Endpoint kinds |
| --- | --- | --- |
| Compare | `A ↔ B → ANALYSIS` | A and B are existing Context trees; the result is a saved analysis, not a Context C |
| Update | `SOURCE A → TARGET B` | A and B are existing Context trees |
| Meld, directional | `INCOMING A → BASELINE B` | A and B are existing Context trees; B is also the result target |
| Meld, symmetric | `PEER A + PEER B → RESULT C` | A and B are existing Context trees; C is an eligible empty Context or a validated new exact name |
| Sever | `SOURCE A × CRITERIA B → OUTPUT C` | A and B are existing Context trees with independent scope controls; C is a new exact name |

“Analysis”, “target”, “result”, and “output” remain distinct terms. The common
shell must not label every final position as storage, because that would hide
Compare's targetless artifact and directional Meld's intentional B/result
identity.

## Horizontal choice component

The mode row and Sever's existing exact/subtree scope row now share one small
terminal component: the operation-free `HorizontalChoiceState` and renderer
extracted from the inline Sever code.

Its contract is intentionally narrow:

- options have stable UIDs and display labels;
- exactly one option is active;
- `Left` and `Right` move with clamped, non-wrapping behavior;
- rendering exposes focus, the active marker, and a concise `←/→` hint;
- changing the active option performs no I/O, provider call, persistence, or
  semantic action; and
- callers own the meaning and validation of the selected UID.

Setup mode and Sever scope may treat movement as immediate process-local
selection. Resolution Workbench item options deliberately keep a cursor
separate from a committed choice and therefore must not be forced onto this
immediate-selection contract. Its whole-set strategy row may reuse the
component later, but that is not required to prove the extraction.

This boundary avoids making a visual segmented selector responsible for
review acceptance or durable decisions.

## Setup state and mode transitions

The shell owns only a process-local draft:

- one mode UID when the operation has modes;
- one independent tree state and selected canonical name for each existing
  role;
- one process-local new-name draft for each creatable role;
- whether an existing-or-new role currently names an existing Context or a
  proposed new one; and
- focus and validation-message presentation.

For Meld, switching modes preserves the A and B selections. A C choice or
new-name draft is also retained while C is hidden so that exploratory mode
switching is reversible, but it is excluded from the directional receipt and
must never influence directional validation, provider input, cache identity,
or persistence. If focus was inside C when a switch hides it, focus returns to
the mode row rather than remaining attached to an invisible control.

A mode change clears stale presentation errors and re-evaluates only cheap
local constraints. It does not load a comparison, create a Context, replace a
saved session, or start an operation.

## Focus and key grammar

- The mode row, when present, is the first focusable region.
- `Tab` and `Shift-Tab` move among the mode and active endpoint panes.
- `Left` and `Right` change a focused horizontal choice; inside a Context tree
  they retain the shared collapse/expand meaning.
- `Up` and `Down` move within a tree. Sever may still move `Up` from the first
  tree row into that role's scope selector.
- `Enter` or `Space` selects the current existing Context row.
- A new-name field remains a one-line exact editor.
- `F` finishes setup and asks the operation adapter to produce its typed
  receipt. `Q` or `Escape` cancels without creating or replacing anything.

The footer is derived from the focused component so the same arrow keys never
advertise two meanings simultaneously.

## Adapter and receipt boundary

The common shell returns a presentation draft with stable role IDs. It does
not construct command-line arguments and is not an authorization receipt.
An operation adapter converts the draft into an operation-owned typed receipt:

- Compare: ordered A/B names;
- Update: source/target names;
- Meld: mode plus A/B, and C/create only for symmetric mode; and
- Sever: source/criteria names, both descendant-scope flags, and new output
  name.

The adapter owns cross-role validation and user-facing role terminology. The
operation then reloads and freezes authoritative state before provider work or
mutation. Existing explicit CLI operands remain supported and go through the
same existing operation validation rather than being routed through a TUI
draft.

## Validation and safety invariants

The common layer may enforce only structural facts: required roles are filled,
selected names came from the frozen selectable catalog, a proposed name has
valid syntax, and declarative distinctness constraints hold. The operation
continues to own all consequential checks:

- Compare re-resolves the ordered pair and freezes the analysis inputs.
- Update applies its endpoint, grant, staged-session replacement, and
  application rules.
- Directional Meld binds B as both baseline and target and rechecks A and B.
- Symmetric Meld requires the saved ordered Compare analysis, rechecks both
  peers, and verifies that C is distinct, eligible, empty/session-free when
  existing, or atomically creatable when new.
- Sever freezes its independently scoped Source and Criteria projections and
  requires a new Output at its established application boundary.

Catalog selection is not authority. A setup receipt is not an Apply receipt.
Every operation reloads the selected identities and performs its existing
digest, grant, lock, CAS, checkpoint, and provenance checks at the established
boundary.

## Component boundaries

The implementation has three layers:

1. `HorizontalChoiceState` and its renderer own generic left/right selection
   presentation.
2. The role-based setup shell owns composition of frozen tree states, editors,
   focus, and process-local draft state.
3. Compare, Update, and Meld adapters own role specs, typed receipts, semantic
   validation, and orchestration. Sever retains its existing typed setup shell
   while sharing the horizontal scope component.

`ContextTreeState` remains the sole owner of namespace cursor and expansion
mechanics. The setup shell composes it rather than copying `mem switch` key
logic. `SessionPicker` remains the saved-work launcher and does not absorb new
session setup.

## Rollout

1. **Completed:** extract and test the horizontal choice component; migrate
   Sever's scope rows without changing Sever behavior.
2. **Completed:** introduce the role-based setup draft and shell with Meld as
   the adaptive-mode consumer. Replace Meld's textual mode prompt and
   sequential pickers while retaining existing orchestration and validation.
3. **Completed:** migrate Update and Compare new-session endpoint collection
   to fixed-mode role specs. Compare also accepts explicit `--from A --to B`
   so its selected A does not require changing the global current Context.
4. **Deferred:** re-express Sever's entire stacked setup using the shared
   role-pane shell. Its existing two-tree layout, typed receipt, scopes, and
   new-only Output contract remain authoritative meanwhile.

Each step must keep non-TTY explicit forms stable and add pipe-input tests for
focus, mode switching, hidden-C exclusion, tree-state independence, cancel,
and typed receipt conversion.

## Alternatives considered

### One sequential picker per operand

Rejected as the default TTY flow because it hides the complete operation
shape, makes role mistakes easy, and cannot explain Meld's changing target
contract while the user chooses endpoints.

### Make directional and symmetric separate launcher commands

Rejected for now because they are already two authority modes of Meld and
share the same saved-session surface. A visible process-local mode selector
keeps the distinction explicit without inventing another command hierarchy.

### Reuse Resolution Workbench option selection wholesale

Rejected because issue options may distinguish cursor movement from committed
review choice. Setup mode and scope selection are immediate, reversible local
state and must not inherit review acceptance semantics.

### Return executable argv from the common shell

Rejected because argv would encode operation semantics inside presentation and
could tempt callers to recursively invoke Typer. Typed adapters preserve the
existing controller and validation boundaries.

## Intentional limitations

- This design does not change Meld's requirement for a saved ordered Compare
  before a symmetric session can start. Endpoint selection itself remains
  process-local until that check succeeds.
- It does not make Compare produce a Context result.
- It does not add a third target to directional Meld.
- It does not merge Ground's conversational Context planning or frozen exact
  approval protocol into the session setup shell.
- Atomize remains a later integration target.

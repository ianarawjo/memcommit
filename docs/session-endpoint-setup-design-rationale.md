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

 MODE · ←/→ SELECT
 ┌──────────────────────────────┐  ┌───────────────────────┐
 │ ✓ SYMMETRIC · A + B → C      │  │   DIRECTIONAL · A → B │
 └──────────────────────────────┘  └───────────────────────┘
 MEANING · A and B are equal peers. The result is separate C.

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
| Atomize | `INPUT A → OUTPUT B` | A is one existing ordinary local Context; B is either the same Context for in-place application or a validated new exact Context name that preserves A |
| Compare | `A ↔ B → ANALYSIS` | A and B are existing Context trees with independent, default-off reach controls; the result is a saved analysis, not a Context C |
| Update | `SOURCE A → TARGET B` | A and B are existing Context trees; each has an independent, default-off reach control |
| Meld, directional | `INCOMING A → BASELINE B` | A has a default-off reach control; B is a direct authoritative mutation target and intentionally has none |
| Meld, symmetric | `PEER A + PEER B → RESULT C` | A and B have independent, default-off reach controls; C is an eligible empty Context or a validated new exact name |
| Sever | `SOURCE A × CRITERIA B → OUTPUT C` | A and B are existing Context trees with independent scope controls; C is a new exact name |

Compare and Update freeze A and B from the same unified readable public
namespace used by other read/source-selection commands. Ordinary local names
and effective READ-granted public names therefore occupy their semantic public
hierarchy together; a Grant attachment is authorization metadata, not a tree
edge. Granted rows display the complete frozen permission set. Query-only
routes are excluded because neither operation accepts concealed query output as
an ordinary Context frame.

Showing a readable granted name does not promise that every downstream role is
authorized. Compare still checks COMBINE and retained-analysis permissions.
Update still checks DERIVE/EXPORT for its source and ACCEPT_DERIVED plus the
required mutation permissions for its target before provider inference or
write. The picker changes discoverability only; normal endpoint resolution,
frozen Grant receipts, revalidation, and application locks remain authoritative.

“Analysis”, “target”, “result”, and “output” remain distinct terms. The common
shell must not label every final position as storage, because that would hide
Compare's targetless artifact and directional Meld's intentional B/result
identity.

## Horizontal choice component

The mode row and every exact/subtree scope row share one small
terminal component: the operation-free `HorizontalChoiceState` and renderer
extracted from the inline Sever code.

Its contract is intentionally narrow:

- options have stable UIDs and display labels;
- exactly one option is active;
- `Left` and `Right` move with clamped, non-wrapping behavior;
- rendering supports a compact segmented row or individual option boxes,
  exposes focus, a stable blue active-value surface, a visible `✓` in the
  boxed selected option, and a concise `←/→` hint;
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

Tab cycling uses the shared `focus_in_order` compatibility route. Cross-surface
Up/Down transitions use `SurfaceFocusController` over the dynamic operation
shape. Endpoint Setup declares its currently visible controls in screen order;
the controller owns focus indexing and non-wrapping boundary movement, while
the endpoint adapter selects the first or last visible Context row when a tree
is entered vertically. New-name input keeps its deliberate special Tab exit.
Help reuses the same controller for its VIEW/list topology.

## Grant-aware selector audit

The endpoint omission exposed a broader risk: a shared tree can look
operation-complete while its caller supplies only `MemoryStore`'s local names.
The audited boundaries are:

| Surface | Catalog contract |
| --- | --- |
| Compare A/B, Update A/B | Local plus effective READ-granted public Contexts; fixed here |
| Meld A/B | Already uses the readable public catalog; directional mutation still validates its local-baseline restriction |
| Sever Source/Criteria | Already projects validated readable Grant rows; Output remains require-new local |
| Switch, List, Find | Already expose or resolve the readable public namespace according to each command's read contract |
| `mem contexts` | Now enumerates the active Profile's complete visible Grant catalog rather than only Grants attached to the current Context |
| Atomize Input / Output | Intentionally local because the implementation analyzes one directly owned Input and either mutates it or creates one directly owned Output; explicit granted Atomize is not implemented |
| Share Source | Intentionally local because Share locks and exports a directly owned active-Profile Context; it does not re-export a granted authority frame |
| Ground Context plan/placement | Intentionally follows Ground's local name-only discovery and separately reviewed binding contract |
| Meld Result, Sever Output | Intentionally existing-local-or-new and require-new-local respectively; neither is a readable source selector |

The common `ContextTreeState` and `choose_context()` utilities remain
catalog-neutral. Their callers must supply the namespace authorized for the
specific role; using the shared widget does not make a local-only catalog
Grant-aware by itself.

The Meld mode selector uses the same boxed horizontal-choice presentation as
Help's `BY KIND` / `A–Z` selector and additionally renders one `MEANING` line
for the active contract. Directional explains that B remains authoritative and
is also the result target. Symmetric explains that A and B are equal peers,
requires their saved ordered Compare, and introduces separate result C.
Context roles use the same blue surface for the retained choice while `›` and
reverse video remain separate browsing-cursor signals; changing a selection
therefore does not move an additional `(●)` column through the namespace tree.
A retained blue choice is not bold after keyboard focus leaves it. Bold
identifies the exact nested control that currently owns input, including a
selected Context, checked descendant scope, mode choice, or Apply control. The
containing endpoint frame keeps its blue border while Tab moves between its
tree and descendant scope, so the pane and within-pane focus levels remain
visible at the same time.

## Setup state and mode transitions

The shell owns only a process-local draft:

- one mode UID when the operation has modes;
- one independent tree state and selected canonical name for each existing
  role;
- one process-local new-name draft for each creatable role;
- one optional caller-owned annotation for selectable rows in a specific role,
  so operation-specific eligibility meaning does not leak into another role
  that renders the same frozen catalog;
- one optional caller-owned new-name suggester driven by the currently checked
  endpoint names; it may refresh an untouched draft, but the first direct text
  edit permanently prevents later endpoint changes from overwriting that draft;
- one optional new-only parent-locator role: its tree chooses an existing
  lexical parent but never turns that Context into the operation target;
- one separately confirmed new name for existing-or-new roles, entered through
  the shared unframed `ExactNameInputControl`, so text merely typed into those
  editors does not become an endpoint choice when focus moves away. A new-only
  parent-locator role instead treats its visible complete exact path as
  authoritative and validates that current value at Apply;
- whether an existing-or-new role currently names an existing Context or a
  proposed new one; and
- focus and validation-message presentation.

New-only placement does not define a second inheritance state inside this
shell. It composes `ContextNameDraftState`, the same operation-neutral state
used by Init's `ContextNameControl`. Source-driven suggestions and explicit
parent choices may update an untouched draft; `record_direct_edit` permanently
hands authority to the exact field for the lifetime of that editor.

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
- `Up` and `Down` treat the visible setup as one top-to-bottom navigation run.
  They move within a Context tree first, then cross its boundary into the
  role's descendant reach control when present and into the next role's first tree
  row. Reverse navigation enters the preceding tree at its last visible row.
  The same boundary rule applies across Compare, Update, Meld, and Sever
  because it lives in the common setup shell. It stops rather than wrapping at
  the mode and Apply edges. A creatable role's new-name field follows its tree
  in this same visible run: Down from the tree's last row enters NEW, Up from
  NEW returns to that tree, and Down from NEW advances to the next control.
  Tab skips the editor when traversing panes, so Down from the role tree is
  the only way to enter it. Once inside, Tab or Shift-Tab may still leave the
  editor without confirming it.
- `Enter` or `Space` selects the current existing Context row. In a new-only
  parent-locator role it instead selects that row as a placement aid. Before
  direct editing, this reparents the exact draft; after the first direct edit,
  the complete typed path remains unchanged and authoritative.
- A mode may opt each readable endpoint into one `THIS CONTEXT ONLY` versus
  `INCLUDE DESCENDANTS` control below a separator. It is exact-only by default;
  Left and Right choose the shared reach, while Enter or Space remains a
  compatibility toggle. The control is in normal Tab order immediately after
  its Context tree. Compare and Update enable it for A and B. Symmetric Meld
  enables it for both peers; directional Meld enables it only for incoming A.
- Down from a creatable role's final tree row opens its one-line exact-name
  editor. Once the editor owns focus, the action row shows `ENTER CONFIRM`.
  Enter validates and confirms the exact name, projects it back into the role
  selector as `NEW · NOT CREATED`, and advances to the next setup control.
  Merely typing and leaving with Tab does not confirm the name. While the
  editor is focused, its footer explicitly renders `Esc back`; Escape returns
  to the role tree without canceling the whole setup. The new-only
  parent-locator variant has no separate projected target row: its visible
  exact field is the draft, so Apply validates that current value even after a
  Tab exit.
- A dedicated `APPLY` frame follows the endpoint panes in the Tab order. Its
  left-aligned `[ PRESS ENTER TO APPLY ]` control makes the final action
  visually distinct from both the endpoint trees and passive footer guidance. `Enter`
  or `Space` on that focused control validates the complete setup and asks the
  operation adapter to produce its typed receipt. There is no hidden finish
  shortcut. Outside the new-name editor, `Q` or `Escape` cancels without
  creating or replacing anything.

The footer is derived from the focused component so the same arrow keys never
advertise two meanings simultaneously.

## Adapter and receipt boundary

The common shell returns a presentation draft with stable role IDs. It does
not construct command-line arguments and is not an authorization receipt.
An operation adapter converts the draft into an operation-owned typed receipt:

- Compare: ordered A/B names plus independent descendant-scope flags;
- Update: source/target names plus independent descendant-scope flags;
- Meld: mode plus A/B, mode-enabled descendant-scope flags, and C/create only
  for symmetric mode; and
- Branch: one existing local Source plus one exact require-new target whose
  parent tree is only a placement aid; and
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

- Compare re-resolves the ordered pair and freezes each selected scope in the
  saved analysis.
- Update applies its endpoint, independently frozen scope, grant,
  staged-session replacement, and application rules.
- Directional Meld may widen incoming A, but binds direct B as both baseline
  and target and rechecks both frozen inputs. Descendant B is deliberately
  unavailable until materialization can preserve each child owner instead of
  moving child Memories into the root baseline.
- Symmetric Meld requires the saved ordered Compare analysis with the exact
  same A/B scope flags, rechecks both peers, and verifies that C is distinct,
  eligible, empty/session-free when existing, or atomically creatable when new.
- Sever freezes its independently scoped Source and Criteria projections and
  requires a new Output at its established application boundary.

Catalog selection is not authority. A setup receipt is not an Apply receipt.
Every operation reloads the selected identities and performs its existing
digest, grant, lock, CAS, checkpoint, and provenance checks at the established
boundary.

## Component boundaries

The implementation has three layers:

1. `HorizontalChoiceState` remains the left/right compatibility facade over the
   common `SelectionOption`, `FlatSelectionState`, and checked-card renderer, while
   `ContextReachState` fixes the shared `THIS CONTEXT ONLY` versus
   `INCLUDE DESCENDANTS` vocabulary and presentation.
2. `ContextTreeState`, `ContextSelectionState`, and the common row renderer own
   namespace cursor/expansion, checked values, and row geometry respectively.
   The role-based setup shell composes those controls with optional
   per-mode/per-role descendant controls, editors, focus, and process-local
   draft state.
3. Compare, Update, and Meld adapters own role specs, typed receipts, semantic
   validation, and orchestration. Sever retains its existing typed setup shell
   while sharing the same Context reach component.

These components live together under `memcommit.context_targeting.tui`.
`ContextTreeState` remains the sole owner of namespace cursor and expansion
mechanics, and `ContextSelectionState` remains the checked-value owner. The
setup shell composes them rather than copying `mem switch` key logic.
`SessionPicker` remains the saved-work launcher and does not absorb new session
setup.

## Rollout

1. **Completed:** extract and test the horizontal choice and Context reach
   components; migrate Sever and the role-based endpoint shell without
   changing their typed scope receipts.
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
- Atomize does not expose descendant scope in this setup. Its semantic and
  apply contracts remain bound to the selected Input's direct Memory frame.

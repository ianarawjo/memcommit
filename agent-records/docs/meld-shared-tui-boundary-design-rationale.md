# Meld shared TUI boundary

> Current contract (2026-08-31): Endpoint Setup remains applicable, but new
> candidate sessions render decisions through Resolve's compact workbench with
> a `MELD` label. References below to the saved Meld Resolution workbench apply
> only to retained historical session presentation.

## Motivating problem

Meld still entered terminal presentation through two command-owned modules:
`commands.endpoint_setup_flows` assembled its A/B/C launch screen and
`commands.meld_shell` adapted a saved session into the shared Resolution
Workbench. This left an otherwise terminal-independent Meld application
boundary coupled to the historical command package.

The launch shape is wider than a fixed two-role picker. Symmetric Meld exposes
`A + B -> C`, disables direct-Memory focus, and allows C to be either an
eligible existing empty Context or a confirmed new exact Result Context name.
Directional Meld exposes only `A -> B`, gives A and B different authority
labels, and may focus one direct Memory when descendant reach is off.

## Shared component contract

`console.tui.components.endpoint_setup` owns only the reusable interaction
mechanics:

- mode-dependent active role order and role labels;
- mode-dependent descendant and direct-Memory controls;
- explicit confirmation of an exact new Context name, rendered `NOT CREATED`;
- omission of hidden roles and hidden scope state from the returned typed
  draft; and
- dynamic focus traversal over only the controls visible in the selected mode.

The component does not discover Contexts, decide Meld authority, connect a
provider, create a session, or create the new Context. A new-name draft is
process-local and has `create=True`; the Meld application layer remains the
only code allowed to validate and materialize that reviewed result.

Mode changes clear a direct-Memory choice when the new mode does not expose
Memory focus. This prevents an invisible narrower scope from surviving in the
executable draft. Backspace remains ordinary text deletion while the exact-name
field owns focus.

## Compact Meld form

Meld setup is a short form, not an analysis workbench. Permanently framing a
Context tree, descendant range, and Memory list for every endpoint expanded a
five-row decision into a full terminal canvas and gave supporting navigation
more visual weight than the request being constructed. Shorter labels inside
the same boxes did not solve that hierarchy problem.

Meld therefore opts into the shared Endpoint Setup's `FORM` layout.
Its stable draft contract is projected through five persistent rows:

1. `MODE` chooses `SYMMETRIC · CREATE SEPARATE RESULT` or
   `DIRECTIONAL · UPDATE EXISTING` with Left/Right;
2. `FROM` accepts the exact A Context name;
3. `WITH` accepts symmetric peer B, while directional mode relabels the same B
   operand as `TO · BASELINE + RESULT`;
4. symmetric `TO` accepts either an eligible existing empty Context or a new
   exact name; and
5. `START MELD` constructs the existing typed draft and returns it to the CLI
   caller, which starts Meld analysis/session execution.

The visible operand labels are only `FROM`, `WITH`, and `TO`. Peer, incoming,
baseline, and Result meaning remains in the selected mode's typed A/B/C role
contract instead of being repeated beside every input. The label column sizes
to those short tokens so the fields begin near the left edge, and every exact
name field renders a fixed `› ` prompt. This keeps the fields visually writable
without restoring boxes or changing their direct-input semantics.

Every A/B/C operand remains a writable one-line field backed by the already
frozen, role-authorized catalog, so each position can be replaced by typing an
exact name directly. Matching names appear only while the person types.
When an existing candidate is available, an explicit `[ BROWSE ]` focus stop
appears beside that field. Tab moves to it and Enter transiently opens the
shared Switch-style Context tree with the role's complete allowed existing
catalog; Enter copies one exact name back and Escape returns to the visible
trigger without changing the operand. For A/B that catalog is the frozen
readable namespace; for C it contains only eligible empty Result Contexts. A C
with no existing eligible target has no inert Browse control, and new C names
remain direct input rather than appearing as if they already exist. The
transient browser and completion are presentation, not new authority, and
final validation still requires the role's exact existing set or its
operation-owned new-name validator. C derives `create=False` for an eligible
existing empty name and `create=True · NOT CREATED` for a validated new name,
so it needs no separate target-kind selector.

An unfilled C says `CHOOSE EMPTY OR ENTER NEW NAME` when at least one eligible
existing empty Context is exposed by Browse; without one it narrows to `ENTER
NEW NAME` and omits the inert trigger. `ENTER NEW NAME` maps to a process-local
exact-name draft. The copy deliberately avoids `CREATE NEW`: setup records
creation intent but does not create the Context at this screen.

Each A/B descendant flag remains an independent checked control on the same
row. Directional Memory focus is summarized on that row and expands its frozen
direct-Memory choices only on demand; closing the detail returns to the same
five-row form. Descendant reach still clears direct-Memory focus, symmetric
mode still disables it, and changing modes still clears a Memory identity the
new mode cannot represent. The executable draft and CLI mapping therefore
receive the same mode, reach flags, direct-Memory selector, and result intent.

The compact form has two distinct spatial axes. `Up` and `Down` move between
the persistent `MODE`, endpoint, and `START MELD` rows, regardless of whether
the current endpoint-row focus is its exact input, Browse action, descendant
control, or Memory action. `Left` and `Right` move between the non-editor peer
controls drawn on one endpoint row, while `Tab` and `Shift-Tab` retain the
complete traversal fallback. Exact-name inputs keep ordinary Left/Right caret
ownership, the Mode choice keeps its own Left/Right selection, and an opened
Context tree keeps Left/Right expansion. Because descendant reach is rendered
as one checked control rather than two horizontal choices, Space or Enter now
changes that value; using Left/Right for both the value and the surrounding row
made it impossible to reach Memory spatially without first broadening the
scope and disabling exact-Memory selection. A visible completion menu, opened
Context catalog, or opened Memory list temporarily owns its own navigation;
reaching a Memory-list vertical edge closes that transient detail and continues
to the adjacent persistent row, while Left closes the detail. This separation
also prevents a Down press from moving sideways and prevents the Memory list
from consuming arrows indefinitely at its edge. Typed draft semantics are
unchanged.

Browse and direct editing are two presentations of the same exact endpoint
field, not separate staged values. Choosing a Context in Browse replaces that
row's writable text, then returns focus to Browse; Left returns to the field so
the chosen name can still be edited in place. While the field owns focus,
Left/Right remain ordinary caret movement until Right reaches the end of the
name. A further Right then crosses the visible boundary into Browse, while Tab
remains the exhaustive traversal fallback. The runnable command and completion
receipt are rebuilt from the current field text, which ensures both a catalog
choice and a later direct correction change the actual FROM/TO operands rather
than only their display labels.

The saved Resolution Session keeps its stacked topology: Viewer, conditional
Responses, Items, optional Save Location, and To Do. Its response choices are
therefore an Up/Down sequence, not a Left/Right option strip. The session must
not advertise the retired `Left/Right option` grammar after choices move into
Responses, and an unsupported horizontal key now explains the correct vertical
or Tab path instead of being consumed silently. Left/Right remains meaningful
only for controls that visibly own horizontal semantics, including Impact
rationale disclosure, Resolve All strategy, and Save Location tree expansion.

The compact form renders in the terminal's main buffer and requests only its
visible rows. It does not enter an alternate full-screen buffer or keep a
flexible blank spacer merely to fill the viewport; terminal history above the
launcher remains intact. On completion it erases only its own live form before
the caller begins Meld. This boundary is specific to `FORM`; saved
Meld analysis and Resolution workbenches still own full-screen presentation.

`START MELD` is intentionally concrete. There is no intermediate “Meld
planning” screen: the setup component returns a process-local receipt, then
`commands.meld` prepares the start, connects a provider when required, creates
or resumes the session/Result under its existing boundaries, and opens review.
The component itself still performs none of that work.

`FORM` is an explicit shared-component opt-in rather than a Meld-owned
parallel request model. Other endpoint consumers retain `WORKBENCH`, including
their established framed trees and keyboard paths, until their own interaction
evidence is reviewed.

## Operation adapter boundary

The intended dependency direction is:

```text
commands.meld (CLI orchestration)
  -> commands.meld.endpoint_setup (typed setup and frozen readable authority)
  -> commands.meld.workbench (saved-session presentation)
  -> console.tui.components (operation-neutral mechanics)
```

The CLI may open its workbench adapter, but the adapter does not invoke the
CLI. Meld runtime, provider, cache, receipt, and Apply semantics remain outside
this relocation. The operation-specific setup and saved-session presentation
belong to the Meld command package; only operation-neutral endpoint mechanics
move to `console.tui.components`, while the shared Resolution workbench remains
under `interfaces.tui` pending its separate ownership review.

## Verification boundary

The migration requires three forms of evidence:

1. typed contract tests for mode/role capability projection and new-name
   invariants;
2. parity and operation tests proving the same Meld requests, reviews, and
   applications survive the import relocation; and
3. an ordered 180x52 color PTY capture covering setup entry, mode/endpoint
   transitions, result-name confirmation, the typed setup receipt, saved-session
   review, and read-only state inspection. Existing end-to-end captures retain
   exact Apply and durable Result evidence because application semantics did
   not move in this change.

The screenshots are behavior evidence, not a second implementation. They must
record exact keys, terminal size, profile/current Context, and durable mutation
at each step.

The relocated Resolution Viewer also follows the shared read-only clipboard
contract: lowercase `y` copies the focused semantic unit and uppercase `Y`
copies the complete current document. Both keys are active only while the
Viewer owns focus; they do not submit a response or change session state.

## Progress

- `1b0e6ae8` extended the shared Endpoint Setup contract and proved symmetric
  and directional drafts independently of Meld orchestration.
- `8e836b23` and `9a701079` moved Meld setup behind its operation adapter and
  exposed the frozen setup projection used by Grant-aware regression tests.
  Meld setup now freezes readable authority in `commands.meld_setup`, projects
  only typed values through `interfaces.tui.operations.meld.setup`, and enters
  the existing application boundary with the same receipt fields. The legacy
  `endpoint_setup_flows` module no longer owns Meld setup behavior.
- `ba08ecc1` moved the saved-session workbench to
  `interfaces.tui.operations.meld.screen`. `commands.meld` enters that adapter
  directly, while `commands.meld_shell` is an import-only compatibility facade.
  The relocation preserves the current Resolution Workbench projection and
  does not move provider, cache, receipt, or Apply semantics into presentation.
- The later command-package consolidation moved the setup types and endpoint
  projection into `commands.meld.endpoint_setup` and the saved-session adapter into
  `commands.meld.workbench`. It removed both the operation-specific
  `interfaces.tui.operations.meld` package and the `commands.meld.shell`
  facade. Public receipt and action shapes, provider/session/Apply boundaries,
  and visible interaction behavior are unchanged. Existing captures therefore
  remain historical evidence of that behavior and were not rewritten merely
  to replace their recorded module path.
- `bb61fd9d` recorded the physical TUI migration separately from the still
  command-owned provider, cache, session-lifecycle, and Apply boundaries.
- `ef48b073` moved Compare report rendering to a neutral presenter, and
  `adad4cda` moved the established Resolution Session implementation under the
  interface workbench owner. Both old command paths remain import-only
  compatibility facades.
- `84bd82a3` split the terminal primitive facade into narrow interface-owned
  frame, input, report-card, tree-row, and viewport components.
- `935ec9b5` moved the remaining Resolution dependencies—Help, Save Location,
  and semantic detail—under `interfaces.tui`. An AST-based regression test now
  rejects every `memcommit.adapters.interfaces` import of `memcommit.adapters.console.commands`.
- `agent-records/docs/screenshots/mem-meld-shared-tui-20260815` records 24 ordered 180x52
  true-color PTY states for both setup shapes and the relocated session screen.
  The captured setup receipts are process-local, sources and Result remain
  byte-identical, no checkpoint or Meld session is created, and provider calls
  remain zero. The final migration regression sets pass with 340
  Meld/component/Resolution boundary tests, 10 Grant-focused tests, and 35
  Study-prewarm tests.
- The setup entry now uses the shared five-row compact form. Contract tests
  cover independently typed A/B/C names, the minimal visible role labels, the
  role-scoped full-catalog browser, existing and new C names, symmetric A/B
  descendant reach, all four directional A/B descendant combinations, and
  directional direct-Memory focus so the reduced presentation cannot drift
  from the existing request fields.

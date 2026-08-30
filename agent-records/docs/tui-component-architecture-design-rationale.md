# Terminal component architecture design rationale

## Status

Implemented for the complete terminal adapter ownership move. Low-level
terminal mechanics, reusable controls, Viewer and Workbench compositions,
selection, and response presentation now have one physical owner under
`memcommit.adapters.console.terminal`. The former `console.tui`,
`console.responses`, `console.selection`, and `adapters.interfaces` packages
are removed rather than retained as compatibility facades.

Last reviewed: 2026-08-28.

## Motivating problem

The repository already shared substantial terminal behavior, but its lowest
visual contracts were owned by the former `memcommit.adapters.console.shared.tui_primitives` and adjacent
command modules. Selection, Context targeting, result workbenches, and other
surfaces therefore imported `commands` even when they did not depend on a
command. Adding another operation screen would either deepen that reverse
dependency or duplicate frame, focus, scrolling, and text-layout behavior.

The target is a component system organized by behavior contracts, not one file
per visible rectangle. Operations should compose shared viewers, while CLI and
TUI presentations remain sibling adapters over one typed application result.

## Chosen structure

```text
memcommit/adapters/console/
  entrypoint.py                 Typer assembly boundary
  router.py                     console dispatch and adapter selection
  clipboard.py                  operating-system clipboard boundary
  commands/                     operation-specific console orchestration
  coordination/                 nonvisual cross-command coordination
  terminal/
    core/                       capabilities, palette, text, keys, buffers
    components/                 controls and composite terminal surfaces
      selection/                reusable choice state and rendering
      responses/                reusable response state and rendering
      semantic_viewer/          typed semantic Viewer composition
      read_only_viewer/         generic read-only Viewer composition
      resolution/               Resolution workbench compositions
      endpoint_setup/           endpoint control and shared setup flows
      history/                  history picker, browser, and presentation
      command_editor/           model, form, live control, rendering, approval
      operation_context_scope_editor/
                                selectors and editors for operation scope
      context_picker/           Context/direct-item terminal picker
        model.py                terminal row and receipt contracts
        projection.py           Context and clipboard projections
        preview.py              lazy preview cache and navigation
        rendering.py            formatted row/detail rendering
        dialog.py               full-screen keys, layout, and lifecycle
```

Dependencies run from command adapters and composite components toward narrow
components, then toward `terminal.core`. Core never imports components, and
terminal components never import command adapters. Help connects its
command-owned inventory to the reusable session component through an explicit
backend registration instead of reversing that direction. Existing callers
import the narrow owning package directly, and the retired
`commands.semantic_viewer`, `commands.surface_focus`,
`commands.tui_text_layout`, `commands.read_only_viewer`, and
`commands.understanding_render` modules are removed rather than retained as
permanent compatibility facades.

The former `interfaces.tui` and `console.tui` paths are removed rather than
retained as forwarding packages. `terminal/components` is a component-library
boundary: a small behavior can remain one module, while a richer control may
group model, rendering, and interaction behind one package API. Viewer and
Workbench are component roles, not additional top-level adapter hierarchies.
`console.coordination` consequently retains only nonvisual command mechanics
such as operand resolution, command grouping, and transfer arguments.
The name replaces `console.shared` because reuse is only a relationship, while
coordination states the package's responsibility at the console-adapter boundary.
The existing flat layout and its two established concept packages remain intact;
this rename does not introduce speculative subcategories or change behavior.

`router.py` deliberately remains at the console root. It chooses among console
adapter routes and therefore sits beside `entrypoint.py`; it is neither a
terminal capability nor an operation-specific command implementation.

The complete Context picker is also a terminal component. Core Context
targeting retains `ContextTreeState`, exact/subtree reach, selection state,
name-draft state, and typed target values. Prompt-toolkit selectors and editors
are owned by `terminal.components.operation_context_scope_editor`; preview
rows, clipboard projection, and action receipts are owned by
`terminal.components.context_picker`. Moving `DirectMemorySelectorControl`
with the other operation-scope controls removes the former core owner of a
component that already depended on terminal preview rows. The range-selection
state still contains its established row projection and therefore imports the
terminal tree renderer; separating that state/projection seam is a later
internal cleanup, not part of this behavior-preserving ownership move.

`memcommit.bootstrap` is the only module that knows both the plain Summarize
presenter and the Summarize TUI presenter. The current Typer command asks that
composition root for a runner; neither presenter imports or invokes the other.

## Summarize console contract

One invocation constructs one typed `SummarizeRequest`, then the router gives
the selected sibling adapter control of when execution begins:

- automatic mode executes the complete current-or-explicit Context request in
  the line-oriented terminal flow, even when input and output are interactive;
- `--plain` explicitly selects that same scripted renderer;
- `--tui` requires an interactive terminal and fails before Store construction
  or provider connection when that capability is absent, then exposes the
  Recent/Context/range setup as an additional action; and
- the TUI can cancel before execution; an individual Run invokes the
  application once, while `BOTH` visibly invokes direct then recursive and
  publishes only the complete pair; and
- `--copy` remains a post-result presentation effect and creates no receipt or
  structured mutation stage; Viewer `y`/`Y` copies the focused scope or complete
  document through the same injected plain-text boundary and likewise creates
  no structured stage.

The TUI adapter freezes one Profile-wide readable catalog before showing the
shared Context selector. The reach control orders `BOTH`, exact, and
descendants above it; Context owns initial focus. The empty Summary frame below
Context owns Run, and the result replaces that action in place. It maps one
result or the typed direct/recursive pair to `SemanticViewerDocument`. It does not parse plain terminal
output or change durable state. The adapter may invoke the injected application
callable only after the explicit action; source opening, authority validation,
provider connection, and freshness checks remain inside the runtime path.
Direct versus recursive reach is copied into a new application request rather
than becoming hidden presentation state.

## Resolution lower-component boundary

The deterministic Merge/Dedup/Resolve workbench and the richer saved-session
Resolution shell intentionally retain different semantic models. They already
share frame chrome, surface focus, flat choice state, response-row rendering,
exact command review, and scrollbar mechanics. The remaining duplicated
plain-text projection is now owned by
`components.plain_text_clipboard.projection`:

- style fragments and cursor anchors are stripped by one pure function;
- two anchors delimit the focused semantic unit;
- a legacy single anchor falls back to its visual line; and
- whole-document projection ignores cursor anchors and preserves all text.

The typed Semantic Viewer adds only an exact-section adapter over that
primitive. The deterministic Resolution shell therefore keeps its historical
`y` behavior of copying the complete focused section even when the section's
viewport block has a start-only anchor, while the saved-session shell keeps
its rendered-fragment focus semantics. Both `Y` paths use the same complete
projection primitive. Neither projection writes the clipboard itself or owns
the operation's decision about which semantic document is copyable.

The deterministic Viewer also adopts the shared wrapped-row scrollbar used by
the saved-session Viewer. Long Memory and evidence lines now use the same
visual-row thumb calculation without changing item identity, focus order, or
application behavior.

## Invariants

1. Application and runtime modules remain independent of Typer,
   prompt-toolkit, terminal capability, and rendering state.
2. Shared component implementations have one owner. A removed command path is
   not reintroduced as a facade merely to avoid migrating a caller.
3. A component owns reusable interaction mechanics; an operation adapter owns
   labels and projection from its typed result.
4. Forced TUI eligibility is checked before catalog or use-case execution, and
   closing setup performs no semantic or durable work.
5. The semantic Viewer remains read-only. Closing or moving focus cannot apply,
   checkpoint, copy, or otherwise mutate a Context.
6. Package discovery must include every normal `memcommit` subpackage so source
   and installed-wheel behavior cannot diverge by silently omitting components.
7. Focused/complete text projection is pure and separate from the operating-
   system clipboard writer; cursor anchors are presentation mechanics, not
   copied content.
8. `core` cannot import `components`; a component package publishes its narrow
   composition surface without absorbing operation validation, provider,
   persistence, receipt, or Apply behavior.

## Alternatives considered

- **Leave forwarding modules under `commands`.** This would make old imports
  continue to work but preserve the misleading dependency direction and allow
  new code to keep using the obsolete owner. All known consumers were migrated
  instead.
- **Create a file for every visual rectangle.** Visual shape alone does not
  define reuse. Frame chrome, scrolling, focus, and typed semantic documents
  are separated because their behavior and tests differ.
- **Build every Summarize control directly from prompt-toolkit widgets.** That
  would prove only a new screen, not shared composition. Summarize instead
  composes the existing Context selector and reach state with the semantic
  Viewer controller; only its screen topology, labels, and Run meaning remain
  operation-owned.
- **Keep Viewer, Workbench, or Session as sibling top-level directories.**
  Those names describe composition roles rather than independent media or
  adapter boundaries. Keeping them as named composite packages under
  `terminal.components` preserves their semantic models without adding a
  second hierarchy.

## Verification evidence

- 90 focused Summarize/router/component/architecture and Grant tests pass for
  the Context-first, three-range, dual-result and scoped-copy workbench slice.
- 1,258 existing TUI-consumer tests pass across bounded partitions after the
  import migration.
- The later console-TUI ownership move passes 85 focused architecture and
  primitive tests plus 834 tests selected from every current core/component
  consumer. The old interface package directories and imports are rejected
  mechanically.
- Architecture tests reject imports from retired command paths, reject
  `interfaces -> commands` dependencies, reject the former physical core and
  component owners and import paths, enforce `core -> components`, and ensure
  the Summarize adapter composes the shared Context-summary workbench instead
  of raw layout widgets.
- A real color-capable 180×52 PTY trace records Context-first entry, the empty
  Summary Run action, all three range choices, direct and recursive result
  sections, focused and complete clipboard projections, cancellation before
  execution, byte/checkpoint verification, and the noninteractive plain route
  under `agent-records/docs/screenshots/mem-summarize-context-first-workbench-20260813/`.
- The later routing trace under
  `agent-records/docs/screenshots/mem-summarize-immediate-routing-20260821/` records immediate
  current and explicit Context summaries without alternate-screen entry, plus
  the same workbench as an explicit `--tui` action and unchanged Store bytes.
- A built wheel contains the new interface hierarchy; an isolated
  `uvx --from <wheel>` environment runs the installed `mem summarize --help`
  and resolves the frame component from site-packages.
- The exact commit tree's repository-wide run reached 2,931 passes; its 38
  failures and 39 errors are the separately recorded Task 2 lock, Atomize
  capture, and obsolete Find-test baseline, with no failure in this slice.
- The Resolution lower-component migration passes 287 focused tests across
  fragment/section projection, both workbench shells, Merge, Dedup, Resolve,
  Meld, Forget, and Sever. Existing operation captures remain semantically
  unchanged because valid focus, choice, review, and Apply topology did not
  change.
- The completed physical ownership move passes 250 focused architecture,
  Help-session, endpoint, history, selection/response, Viewer/Workbench,
  ownership, and generated-catalog tests. Mechanical gates reject the old
  `console.tui` and `adapters.interfaces` trees, compatibility facades under
  `console.shared`, `terminal.core -> components` imports, and
  `terminal.components -> commands` imports.

## Remaining boundary

The two Resolution workbench semantic models remain separate component
packages until optional items, comments, drafts, and provider-turn behavior
demonstrate a safe common semantic contract. Physical co-location does not
authorize merging their typed documents or Apply rules. The public Python API
and machine-readable adapter remain separate media gates; this migration
changes import ownership, not their contracts or terminal interaction
behavior.

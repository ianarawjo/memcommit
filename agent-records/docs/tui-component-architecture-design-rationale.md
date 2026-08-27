# TUI component architecture design rationale

## Status

Implemented and verified for the shared frame, focus, scrollable-pane,
plain-text projection, semantic Viewer, read-only Viewer, Context Summary, and
both Resolution workbench shells.

Last reviewed: 2026-08-16.

## Motivating problem

The repository already shared substantial terminal behavior, but its lowest
visual contracts were owned by `memcommit.commands.shared.tui_primitives` and adjacent
command modules. Selection, Context targeting, result workbenches, and other
surfaces therefore imported `commands` even when they did not depend on a
command. Adding another operation screen would either deepen that reverse
dependency or duplicate frame, focus, scrolling, and text-layout behavior.

The target is a component system organized by behavior contracts, not one file
per visible rectangle. Operations should compose shared viewers, while CLI and
TUI presentations remain sibling adapters over one typed application result.

## Chosen structure

```text
memcommit/adapters/interfaces/tui/
  core/                         terminal text layout, style, buffers, keys
  components/
    frame/                      frame model and focused chrome
    focus/                      cross-surface focus controller
    scrollable_pane/            model, navigation, scrollbar, component
    plain_text_clipboard/       projection, writer boundary, result receipt
  viewers/
    semantic/                   typed document, controller, renderer, text, shell
    read_only/                  generic read-only shell
  workbenches/
    context_summary/            Context + reach + semantic result composition
    resolution/                 deterministic and saved-session compositions
  operations/
    summarize/                  picker/reach composition and result projection
```

The dependency direction is `core -> components -> viewers -> operation
adapters`. `memcommit.adapters.interfaces` does not import `memcommit.commands`.
Existing callers import the narrow owning package directly, and the retired
`commands.semantic_viewer`, `commands.surface_focus`,
`commands.tui_text_layout`, `commands.read_only_viewer`, and
`commands.understanding_render` modules are removed rather than retained as
permanent compatibility facades.

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
- **Move every TUI helper at once.** Input controls, tree selectors, and review
  workbenches have different state and safety contracts. They remain in place
  until a vertical slice can migrate and verify each family.

## Verification evidence

- 90 focused Summarize/router/component/architecture and Grant tests pass for
  the Context-first, three-range, dual-result and scoped-copy workbench slice.
- 1,258 existing TUI-consumer tests pass across bounded partitions after the
  import migration.
- Architecture tests reject imports from retired command paths, reject
  `interfaces -> commands` dependencies, and ensure the Summarize adapter
  composes the shared Context-summary workbench instead of raw layout widgets.
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

## Remaining boundary

This slice now proves process-local Context-tree selection, a three-way
range choice, complete dual-result publication, cancellation before execution,
explicit reruns, scoped/complete plain-text copy, and a read-only result Viewer.
It does not prove editable text input, review/Apply,
cache/receipt, or CAS behavior through the new operation-adapter hierarchy. The
two Resolution workbench semantic models also remain separate until optional
items, comments, drafts, and provider-turn behavior demonstrate a safe common
contract. The public Python API and machine-readable adapter remain separate
gates.

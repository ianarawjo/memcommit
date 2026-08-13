# TUI component architecture design rationale

## Status

Implemented and verified for the shared frame, focus, scrollable-pane, semantic
Viewer, read-only Viewer, and Summarize operation adapter.

Last reviewed: 2026-08-13.

## Motivating problem

The repository already shared substantial terminal behavior, but its lowest
visual contracts were owned by `memcommit.commands.tui_primitives` and adjacent
command modules. Selection, Context targeting, result workbenches, and other
surfaces therefore imported `commands` even when they did not depend on a
command. Adding another operation screen would either deepen that reverse
dependency or duplicate frame, focus, scrolling, and text-layout behavior.

The target is a component system organized by behavior contracts, not one file
per visible rectangle. Operations should compose shared viewers, while CLI and
TUI presentations remain sibling adapters over one typed application result.

## Chosen structure

```text
memcommit/interfaces/tui/
  core/                         terminal text layout, style, buffers, keys
  components/
    frame/                      frame model and focused chrome
    focus/                      cross-surface focus controller
    scrollable_pane/            model, navigation, scrollbar, component
  viewers/
    semantic/                   typed document, controller, renderer, shell
    read_only/                  generic read-only shell
  operations/
    summarize/                  result projection and launch adapter only
```

The dependency direction is `core -> components -> viewers -> operation
adapters`. `memcommit.interfaces` does not import `memcommit.commands`.
Existing callers import the narrow owning package directly, and the retired
`commands.semantic_viewer`, `commands.surface_focus`,
`commands.tui_text_layout`, `commands.read_only_viewer`, and
`commands.understanding_render` modules are removed rather than retained as
permanent compatibility facades.

`memcommit.bootstrap` is the only module that knows both the plain Summarize
presenter and the Summarize TUI presenter. The current Typer command asks that
composition root for a runner; neither presenter imports or invokes the other.

## Summarize console contract

One invocation constructs one typed `SummarizeRequest` and executes the
application callable at most once. The router then presents the returned
`SummarizeResult`:

- automatic mode chooses the TUI only when input and output are interactive;
- `--plain` always uses the scripted renderer;
- `--tui` requires an interactive terminal and fails before Store construction
  or provider connection when that capability is absent; and
- `--copy` remains a post-result presentation effect and creates no receipt or
  structured mutation stage.

The TUI adapter maps the result directly to `SemanticViewerDocument`. It does
not parse plain terminal output, reopen Contexts, call a provider, or change
durable state. Direct versus recursive reach stays in the application request,
not in the presentation router.

## Invariants

1. Application and runtime modules remain independent of Typer,
   prompt-toolkit, terminal capability, and rendering state.
2. Shared component implementations have one owner. A removed command path is
   not reintroduced as a facade merely to avoid migrating a caller.
3. A component owns reusable interaction mechanics; an operation adapter owns
   labels and projection from its typed result.
4. Forced TUI eligibility is checked before executing the use case, so an
   unavailable presentation route cannot partially execute semantic or durable
   work.
5. The semantic Viewer remains read-only. Closing or moving focus cannot apply,
   checkpoint, copy, or otherwise mutate a Context.
6. Package discovery must include every normal `memcommit` subpackage so source
   and installed-wheel behavior cannot diverge by silently omitting components.

## Alternatives considered

- **Leave forwarding modules under `commands`.** This would make old imports
  continue to work but preserve the misleading dependency direction and allow
  new code to keep using the obsolete owner. All known consumers were migrated
  instead.
- **Create a file for every visual rectangle.** Visual shape alone does not
  define reuse. Frame chrome, scrolling, focus, and typed semantic documents
  are separated because their behavior and tests differ.
- **Build Summarize directly from prompt-toolkit widgets.** That would prove
  only a new screen, not shared composition. Summarize therefore contains only
  a result adapter and delegates the shell to the semantic Viewer.
- **Move every TUI helper at once.** Input controls, tree selectors, and review
  workbenches have different state and safety contracts. They remain in place
  until a vertical slice can migrate and verify each family.

## Verification evidence

- 93 focused Summarize/router/component/architecture and Grant tests pass in
  the exact commit tree.
- 1,258 existing TUI-consumer tests pass across bounded partitions after the
  import migration.
- Architecture tests reject imports from retired command paths, reject
  `interfaces -> commands` dependencies, and ensure the Summarize adapter
  composes the shared Viewer instead of raw layout widgets.
- A real color-capable 180×52 PTY trace records entry, section focus changes,
  close verification, and the noninteractive plain route under
  `docs/screenshots/mem-summarize-tui-20260813/`.
- A built wheel contains the new interface hierarchy; an isolated
  `uvx --from <wheel>` environment runs the installed `mem summarize --help`
  and resolves the frame component from site-packages.
- The exact commit tree's repository-wide run reached 2,931 passes; its 38
  failures and 39 errors are the separately recorded Task 2 lock, Atomize
  capture, and obsolete Find-test baseline, with no failure in this slice.

## Remaining boundary

This slice proves a read-only completed-result Viewer. It does not yet prove
editable input, Context-tree selection, review/Apply, cache/receipt, or CAS
behavior through the new operation-adapter hierarchy. The public Python API and
machine-readable adapter also remain separate gates. A second non-Study slice
should add one of those contracts while reusing this component ownership and
console routing.

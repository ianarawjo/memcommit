# Interactive Context picker

Last reviewed: 2026-08-28.

## Motivation

The semantic ambiguity review already demonstrates that a participant can
navigate a terminal list with concrete arrow-key events. Context navigation
previously required reading a flat catalog, recalling a complete name, and
then typing it into a second command:

```bash
mem contexts
mem switch construction-updates/route-changes
```

This is unnecessarily indirect during a study workflow, especially when
several names share a namespace prefix. `mem switch` without a name therefore
opens a single-choice terminal picker. Supplying a name keeps the original
scriptable behavior, while a leading `.` or `..` explicitly opts into lexical
navigation from the current Context:

```bash
mem switch NAME          # switch to this canonical global name
mem switch               # choose interactively
mem switch .             # stay on and validate the current Context
mem switch ..            # switch to the lexical namespace parent
mem switch ./child       # switch to a child of the current Context
mem switch ../sibling    # switch to a sibling of the current Context
```

`mem contexts` and `mem list` / `mem ls` deliberately do not open this picker.
They render their stable catalog or target-rooted result in terminals and pipes
alike. That keeps interactive Profile navigation distinct from orientation and
listing; the cross-command decision is recorded in
[`context-listing-design-rationale.md`](context-listing-design-rationale.md).

Bare `NAME` deliberately remains global. For example, from
`organization/wiki`, `mem switch facilities` selects the canonical Context
named exactly `facilities`; only `mem switch ./facilities` selects
`organization/wiki/facilities`. This explicit marker preserves existing
scripts and avoids making a name mean different things depending on current
state.

## Interaction contract

The picker derives a slash-delimited tree from the canonical names returned by
`MemoryStore.list_context_names()`. Its compact initial view shows top-level
rows and expands only the exact ancestor chain needed to reveal the current
Context. The current Context is marked with `*` and preselected. With no
current Context, the first catalog Context is selected and its ancestor chain
is expanded.

The representative `180×52` color-PTY record under
[`screenshots/mem-switch-direct-items-participant-20260813/`](screenshots/mem-switch-direct-items-participant-20260813/README.md)
uses the active Participant Profile to contrast six real `VIA EMBED` direct
occurrences with their ordinary lexical child rows and a separate `READ GRANT`
public tree.

The focused disposable-Profile record under
[`screenshots/mem-switch-context-colors-20260820/`](screenshots/mem-switch-context-colors-20260820/README.md)
places a granted public Context, an embedded Context occurrence, and an opaque
reference Context on the same screen and verifies their exact emitted
`xterm-256color` ANSI foregrounds plus cancellation with no durable Profile
change.

- Up and Down move among currently visible rows and stop at the first or last
  row.
- Right expands one complete descendant depth below the selected anchor. The
  first press reveals its direct children, the next reveals grandchildren
  below every expandable direct child, and later presses continue one depth at
  a time. Once the complete subtree is visible, Right moves to the first child.
  Left removes the deepest expanded descendant depth one layer at a time; only
  when no layer remains does it move to the parent. A partially open initial
  current path is normalized at its shallowest missing depth before a deeper
  layer opens. The footer names this control `←→ expand` so the visible
  action is explicit rather than calling the widget itself a tree.
- `A` snapshots the current compact expansion state and expands every branch.
  A second `A` restores that state. If the person selected a descendant that
  was hidden in the snapshot, its ancestors remain expanded so selection does
  not jump or disappear.
- Lowercase `m` toggles read-only direct-item rows only for the selected
  Context. Uppercase `M` shows or hides them for all Contexts and clears prior
  per-Context exceptions, providing a predictable fresh global state. The
  projection preserves persisted order and includes every durable form:
  `memory`, `memory ref`, and `context`. Both embedded Contexts and opaque
  query-only references use the `context` object label; `VIA EMBED` and
  `QUERY ONLY` state how each non-ordinary occurrence can be reached. An
  embedded Context occurrence carries `VIA EMBED`; its separate lexical
  namespace row does not, because name ancestry is not evidence of an Embed
  edge. Query-only references expose only their opaque name, never hidden
  content. Direct-item rows show their short selector and escaped visible
  content, but never become semantic selections or accepted values and never
  change which Context owns the selection. While direct-item rows are visible,
  Up and Down interleave them as
  read-only viewport focus stops between their owning Context and the next
  Context. The same reverse-video focus bar moves from the owning Context onto
  all wrapped lines of the focused item; ordinary Memory rows remain lavender,
  while navigation pointers and ordinary Context rows stay neutral; the three
  special Context categories use the palette below. This is presentation
  focus only—the owning Context remains the semantic selection even though its
  focus bar has moved. Enter on a direct-item
  stop is inert, and Left returns the focus bar to that Context. This
  prevents a long expanded direct-item run from being skipped merely because only
  Contexts are selectable. Content wraps at the
  available terminal width, and every continuation line uses a hanging indent
  aligned with the first line's content after the Memory selector. The wrapping
  prefers whitespace boundaries so ordinary words remain intact; only a single
  token wider than the available content column falls back to character-level
  splitting. Wrapping remains presentation-only, so terminal resizing never
  inserts newlines into stored content. Newly revealed
  Contexts are loaded into a process-local cache only when their effective
  visibility is on. Query-only and otherwise unavailable virtual rows remain
  opaque; their source content is never opened for the preview.
- Outside the moving focus bar, color is limited to three typed words: `GRANT`
  is green, `VIA EMBED` is yellow, and `QUERY ONLY` is purple. The public or
  embedded Context name, selector UID, path, capability summary, punctuation,
  and surrounding tree chrome remain white. Coloring only the semantic token
  avoids turning a whole row into a category banner. Color is never parsed
  back into identity, authority, or selection. When one of these rows receives
  focus, the shared reverse focus treatment temporarily replaces its token
  color so there is only one keyboard target.
- A materialized Context leaf uses `▸`/`▾` for its direct-item presentation
  layer instead of remaining a `·`. Right opens that layer, Left closes it
  before moving to the parent, and read-only browse mode also toggles it with
  Enter. Branch markers continue to describe Context-descendant expansion, so
  the independent `m` control remains available for their direct items.
- Lowercase `y` copies the currently focused semantic row to the macOS system
  text clipboard without closing the picker. A focused Context produces only
  its displayed Context row. A focused direct item produces its displayed selector,
  source annotation when present, and whitespace-normalized content on one
  physical clipboard line; terminal-width wrapping and its hanging indent are
  presentation state and never enter the copied text. Uppercase `Y` produces
  the same result for a focused direct item. For a focused Context it instead copies
  that Context plus only its currently visible descendant rows. A collapsed
  descendant row is included because it is visible, but its hidden descendants
  are not; direct-item rows are included only where their preview layer is
  currently visible. The focused pointer, current marker, branch glyphs,
  indentation, public names, and visible Grant annotations preserve the
  reviewed tree shape. A concise `COPIED` or `COPY FAILED` receipt temporarily
  replaces the ordinary footer without accepting or switching the Context.
- Picker copy writes only plain operating-system clipboard text. It does not
  create the private structured `mem ls --copy` stage: one visible branch may
  intentionally combine participant-owned Contexts and several granted public
  rows, for which a fabricated single-source receipt would be misleading.
  READ-visible granted text already displayed in the picker remains an explicit
  user-controlled disclosure, while query-only content is never loaded or
  copied. The action does not save a Context, item, session, or preference.
  Ordinary terminals reserve Command-C for terminal-owned selection copying
  and do not portably transmit the Command modifier to prompt-toolkit, so the
  semantic copy keys are `y` and `Y`; Ctrl-C retains its existing cancel role.
- In `mem switch`, Enter accepts the selected Context. Read-only consumers of
  the component may instead use Enter only to open or collapse the focused
  branch or direct-item layer. Every displayed row comes from the frozen real
  or granted Context catalog.
- Escape, `q`, or Ctrl-C cancel without changing current state.
- The list body expands to the terminal's available height. When visible rows
  exceed it, prompt-toolkit scrolls around the selected row and displays a
  scrollbar. The footer distinguishes visible rows from total materialized
  Contexts.
- A read-only root ribbon remains pinned above the scrolling body. Expanding
  the current path can reveal many siblings under a high-fan-out parent; the
  ribbon keeps the compact set of top-level starting namespaces visible even
  when those rows themselves have scrolled outside the body viewport.

The picker renders all *currently visible* tree rows into one flexible Window
and marks the selected row as the viewport cursor anchor. It deliberately does
not slice the tree to a fixed row count: that earlier design left unused space
below a twelve-row picker even when a taller terminal could show more. It also
does not start with the entire catalog expanded. In a study Profile with many
descendants under one authority namespace, a fully expanded flat list consumed
the initial viewport and made sibling task roots appear absent even though
scrolling could eventually reach them.

Expansion, direct-item visibility, and selection are process-local presentation
state. They never enter a Context record, Profile, or `state.json`. There is no
`-R` Switch option:
unlike `mem ls -R`, which changes the traversal included in output, the picker
always knows the complete switchable catalog and `A` changes only its current
presentation. Keeping the toggle inside the picker also lets a person inspect
both compact and expanded views without restarting the command.

Only catalog Contexts become tree nodes. A Context is placed below its nearest
real catalog ancestor; if none exists, its complete name is shown as a root.
The picker never synthesizes missing slash prefixes. Profile creation may
separately materialize empty parents when a continuous hierarchy is desired,
but opening the picker never repairs or mutates storage.

The picker returns a name but never writes store state. The common switch path
reloads and validates that name after the picker closes and only then updates
`state.json`. It records both the observed current name and the selected
Context's UID and direct-record digest. The final store compare-and-set holds
the selected Context's write lock and the state write lock, rejects deletion,
replacement, or modification of the selected record, and rejects a concurrent
current-Context change. This prevents a slow picker or relative resolution
from silently overwriting another terminal's later switch.

The namespace tree is also available from
`memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.tree`
as the shared terminal `ContextTree` plus `ContextTreeState` component. It owns the frozen tree,
cursor, visible-row projection, depth-wise expansion and collapse, and
expand-all restore behavior. Terminal `ContextMemoryRow` projections add
read-only direct-item leaves without changing the Context cursor. The shared
state component performs no terminal I/O and assigns no operational role to the
selected name. `choose_context()` in
`memcommit.adapters.console.terminal.components.context_picker` is the
full-screen, single-selection wrapper over that state and can also run in
read-only browse mode. Larger TUIs may embed one or more
independent states and retain their own role, scope, validation, and receipt
contracts. Sever setup uses one state for Source and one for Criteria while
keeping descendant scope and the require-new Output name Sever-owned.

Long direct-item runs reuse the common `NavigationAccelerator` presentation
primitive also used by semantic result reports. Deliberate arrow taps move one
Context-or-item viewport unit, even when several taps arrive quickly. Because
a terminal supplies key presses rather than key-up state, acceleration begins
only after the initial auto-repeat delay and a sustained short repeat cadence
identify a held arrow. Holding the same direction then accelerates the movement
rate to two and five times the terminal repeat cadence. Each intermediate
Context-or-item unit is still visited and invalidated separately;
acceleration never jumps over a semantic row. An interrupted cadence, direction
change, or structural action resets the rate to one. The shared accelerator
owns timing only and never makes a direct item selectable or changes the Context
receipt.

## Dependency map and ownership

Interactive `mem switch` and operation-owned selectors depend directly on the
ordinary/granted Profile catalog and neutral picker. Static orientation and
listing commands depend on their own renderers:

```text
memcommit.adapters.console.entrypoint
├── mem contexts -> commands.contexts.cmd
│   ├── MemoryStore.list_context_names()
│   ├── MemoryStore.current_context_name()
│   └── render the read-only list and current `*` marker
├── mem list -> commands.list_memories.cmd
│   └── render the resolved direct/recursive snapshot
└── mem switch -> commands.switch.cmd
    ├── MemoryStore.current_context_name()       # one command-start snapshot
    ├── when NAME is omitted
    │   ├── MemoryStore.list_context_names()
    │   └── terminal.components.context_picker.choose_context()
    │                                           # returns a name only
    ├── when NAME is supplied
    │   └── bypass the catalog UI and use the operand directly
    ├── commands.switch.setup                     # name -> typed request
    ├── switch_application.switch_context()      # locator/application policy
    └── switch_runtime.MemoryStoreSwitchContextPort
        ├── READ access + full target validation
        └── MemoryStore.set_current_*_if()       # the only switch-state write
```

The neutral Context picker owns tree navigation and exposes separate accepting
and browse-only behavior for consumers that need them. The Switch
application/runtime owns relative resolution, target validation, and mutation.
Static commands neither import the picker nor invoke Switch, avoiding both a
hidden input wait and a human-output dependency.

`choose_context()` accepts caller-owned title and acceptance labels so a
Compare, Update, Ground, or Switch flow does not mislabel selection as another
operation. The lower `ContextTreeState` boundary is preferred when selection
must remain inside an existing full-screen application; launching nested Typer
commands is not an integration mechanism.

`commands/shared/context_picker.py` is now a behavior-free compatibility export.
Production callers import the neutral picker directly, so Ground and other
operations no longer depend on the Switch command layer merely to render the
same frozen names.

The local catalog method scans only ordinary Context records under
`contexts/**/context.json` and validates their minimum identity header, so
query-source records never enter the ordinary namespace. The separate Grant
catalog may expose a query-only public route for orientation, but that row is
opaque and cannot load Memories or become a Switch target. A selected target
is deliberately validated more deeply by `MemoryStore.load()` before the
current pointer changes. The picker catalog can therefore be read cheaply, but
a record with a valid header and malformed internal items may still appear in
the list and then fail closed when selected.

The catalog and current pointer reads are not one atomic snapshot today.
`mem contexts` may show a temporarily stale marker, while `mem switch` captures
the current pointer before opening its independently read name list. A stale
display cannot authorize a stale switch: after selection, Switch reloads the
target and the final compare-and-set rejects both a changed target record and
a changed current pointer.

The lexical resolver itself is operation-neutral and lives in
`memcommit.application.capabilities.context_locator`; Switch owns existence and load validation plus
the final state compare-and-set through `switch_application.py` and
`switch_runtime.py`. Compare uses the same
resolver without inheriting Switch's mutation semantics. The reuse boundary is
documented in
[`context-locator-design-rationale.md`](context-locator-design-rationale.md).

## Terminal and automation boundary

A bare `mem switch` requires an interactive stdin and stdout. In a pipe, test
runner, or other non-TTY environment it fails with an instruction to pass the
Context name explicitly. It must not wait indefinitely for terminal input.
`mem switch NAME` remains noninteractive and unchanged for scripts and agents.
`mem contexts` and List never inspect terminal interactivity and always print
their stable results without waiting for input.

The implementation uses a small prompt-toolkit component rather than the
ambiguity `ReviewSession` shell. The two interfaces share key-handling
conventions, but Context selection has no semantic finding, response,
checkpoint, resumable review state, or persisted tree expansion state.

## Explicit lexical relative navigation

Relative selectors treat `/`-delimited Context names as a navigable lexical
namespace. They are resolved from the full current Context name:

| Current | Selector | Resolved canonical name |
| --- | --- | --- |
| `test/update/from` | `.` | `test/update/from` |
| `test/update/from` | `./` | `test/update/from` |
| `test/update/from` | `..` | `test/update` |
| `test/update/from` | `../` | `test/update` |
| `test/update` | `./to` | `test/update/to` |
| `test/update/from` | `../to` | `test/update/to` |
| `test/update/from` | `../../archive` | `test/archive` |

`.` is the current lexical node; `..` removes one namespace segment; and a
following ordinary segment is appended. One trailing slash is an optional
separator, so `./` equals `.` and `../` equals `..`. Leading parent segments
may be chained. Resolution rejects an attempt to pop above the namespace root,
and a selector that finishes at the unnamed root cannot identify a Context.
Repeated or interior empty segments are rejected rather than silently
canonicalized.

This navigation does not inspect the filesystem working directory and does not
search for a Context that happens to embed the current one. That distinction
keeps the command deterministic because a Context may be embedded in zero,
one, or multiple unrelated Contexts.

Every resolved name must itself be a persisted, loadable Context, not merely a
directory created to hold descendants. Relative switching never creates
missing Contexts. With no current Context, at a namespace boundary, when the
exact target Context is absent, or when the target cannot be loaded, the
command reports the error and leaves current state unchanged.

## Git-style compatibility command

`mem checkout` combines two distinct routes under familiar Git-style syntax;
it is not a complete alias for either operation. Without `-b`, an explicit name
preserves the scriptable `mem switch NAME` behavior and an omitted name opens
the same Switch picker, including its validation, relative-navigation boundary,
granted-view handling, and current-state compare-and-swap. With `-b`, an
explicit name invokes Branch creation and an omitted name opens Branch's
Source-and-name creation control. The dispatcher maintains no second picker or
branch implementation, but its conditional grammar remains a compatibility
surface rather than a third Context operation.

## Limitations and non-goals
- Relative selectors walk only a name namespace. They do not represent an
  embedded-Context relationship, and there is no implicit search for an
  embedding parent.
- Relative switching does not create a namespace ancestor or target. Parent
  creation, if offered by `mem init`, is a separate operation and policy.
- The picker does not yet filter or fuzzy-search names. Collapsing the tree
  keeps unrelated descendants out of the initial viewport, but the process
  still builds its model from every catalog Context. A store with very many
  Contexts needs indexed name search rather than only a collapsible widget.
- The root ribbon is a one-line orientation aid, not a second selection pane.
  An unusually large or wide set of root names can be clipped by the terminal;
  the scrollable tree remains the authoritative picker in that case.
- The global current Context remains the repository's existing single-state
  mechanism. Compare-and-set prevents this command from overwriting a
  concurrent change, but it does not add per-shell current state.
- The atomize workbench remains unrelated to Context selection. It navigates
  typed split, uncertainty, ambiguity, and conflict issues bound to one
  analysis; the switch picker only returns one Context name and has no durable
  response state.

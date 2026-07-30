# Interactive `mem switch` Context picker

## Motivation

The semantic ambiguity review already demonstrates that a participant can
navigate a terminal list with concrete arrow-key events. Context navigation
previously required recalling and typing a complete name:

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

Bare `NAME` deliberately remains global. For example, from
`organization/wiki`, `mem switch facilities` selects the canonical Context
named exactly `facilities`; only `mem switch ./facilities` selects
`organization/wiki/facilities`. This explicit marker preserves existing
scripts and avoids making a name mean different things depending on current
state.

## Interaction contract

The picker presents canonical names from `MemoryStore.list_context_names()`.
The current Context is marked with `*` and preselected.

- Up and Down move the selection and stop at the first or last item.
- Enter accepts the selected Context.
- Escape, `q`, or Ctrl-C cancel without changing current state.
- At most twelve names are rendered at once; the viewport follows the
  selection.

The picker returns a name but never writes store state. The common switch path
reloads and validates that name after the picker closes and only then updates
`state.json`. It records both the observed current name and the selected
Context's UID and direct-record digest. The final store compare-and-set holds
the selected Context's write lock and the state write lock, rejects deletion,
replacement, or modification of the selected record, and rejects a concurrent
current-Context change. This prevents a slow picker or relative resolution
from silently overwriting another terminal's later switch.

The lexical resolver itself is operation-neutral and lives in
`memcommit.context_locator`; Switch owns only picker behavior, existence and
load validation, and the final state compare-and-set. Compare uses the same
resolver without inheriting Switch's mutation semantics. The reuse boundary is
documented in
[`context-locator-design-rationale.md`](context-locator-design-rationale.md).

## Terminal and automation boundary

A bare `mem switch` requires an interactive stdin and stdout. In a pipe, test
runner, or other non-TTY environment it fails with an instruction to pass the
Context name explicitly. It must not wait indefinitely for terminal input.
`mem switch NAME` remains noninteractive and unchanged for scripts and agents.

The implementation uses a small prompt-toolkit component rather than the
ambiguity `ReviewSession` shell. The two interfaces share key-handling
conventions, but Context selection has no semantic finding, response,
checkpoint, or resumable review state.

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

## Limitations and non-goals

- `mem checkout` still requires a name; this change is scoped to the explicit
  argument form and delegates non-branch selection to Switch.
- Relative selectors walk only a name namespace. They do not represent an
  embedded-Context relationship, and there is no implicit search for an
  embedding parent.
- Relative switching does not create a namespace ancestor or target. Parent
  creation, if offered by `mem init`, is a separate operation and policy.
- The picker does not yet filter or fuzzy-search names. Rendering is bounded,
  but `list_context_names()` still enumerates and validates every Context.
  A store with very many Contexts needs an indexed name search rather than a
  larger terminal widget.
- The global current Context remains the repository's existing single-state
  mechanism. Compare-and-set prevents this command from overwriting a
  concurrent change, but it does not add per-shell current state.
- The atomize workbench remains unrelated to Context selection. It navigates
  typed split, uncertainty, ambiguity, and conflict issues bound to one
  analysis; the switch picker only returns one Context name and has no durable
  response state.

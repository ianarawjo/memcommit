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
scriptable behavior:

```bash
mem switch NAME   # validate and switch directly
mem switch        # choose interactively
```

## Interaction contract

The picker presents canonical names from `MemoryStore.list_context_names()`.
The current Context is marked with `*` and preselected.

- Up and Down move the selection and stop at the first or last item.
- Enter accepts the selected Context.
- Escape, `q`, or Ctrl-C cancel without changing current state.
- At most twelve names are rendered at once; the viewport follows the
  selection.

The picker returns a name but never writes store state. The existing switch
path reloads and validates that name after the picker closes and only then
updates `state.json`. This preserves the previous validation boundary and
handles a Context being deleted or damaged while the picker is open.

## Terminal and automation boundary

A bare `mem switch` requires an interactive stdin and stdout. In a pipe, test
runner, or other non-TTY environment it fails with an instruction to pass the
Context name explicitly. It must not wait indefinitely for terminal input.
`mem switch NAME` remains noninteractive and unchanged for scripts and agents.

The implementation uses a small prompt-toolkit component rather than the
ambiguity `ReviewSession` shell. The two interfaces share key-handling
conventions, but Context selection has no semantic finding, response,
checkpoint, or resumable review state.

## Limitations and non-goals

- `mem checkout` still requires a name; this change is scoped to the explicit
  `switch` operation requested for the study workflow.
- The picker does not yet filter or fuzzy-search names. Rendering is bounded,
  but `list_context_names()` still enumerates and validates every Context.
  A store with very many Contexts needs an indexed name search rather than a
  larger terminal widget.
- The global current Context remains the repository's existing single-state
  mechanism. The picker does not add multi-terminal locking or per-shell
  current state.
- Atomize uncertainty now uses the shared semantic review shell, but it remains
  unrelated to Context selection. `mem review atomize` navigates
  `UNCERTAIN / RECONCILE` analysis items and stages per-Memory context or
  comments; the switch picker only returns one Context name and has no durable
  response state.

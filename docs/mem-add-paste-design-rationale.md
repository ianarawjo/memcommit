# `mem add --paste` design rationale

## Intent

`mem add --paste` is an interactive intake mode for notes that are already on
the clipboard. It keeps a large or sensitive-looking paste from flooding the
terminal while retaining the existing rule that every non-empty physical line
becomes one raw Memory record. A line is an intake boundary, not a claim that
the content is semantically atomic.

The terminal view shows only a running summary such as
`[24 lines pasted]`. It never places the captured payload in the editable
control, and the command prints only a count after saving. Users can inspect
the resulting Memories deliberately with `mem ls` or `mem show`.

This is a display and review boundary, not an access-control boundary. Once the
user confirms, the full text is stored in the Context and its checkpoint like
any other Memory. Later commands may display it.

## Command contract

```console
$ mem add --paste
Paste text; each non-empty line becomes one Memory.
[0 lines pasted]  F2/Ctrl-D: review  Ctrl-C: cancel

[12 lines pasted]
Add 12 Memories to 'temp/task-1'? [y/N]:
Added 12 Memories to 'temp/task-1'.
```

- A bracketed paste is captured without echoing its text.
- Multiple paste events are appended in arrival order. A missing newline is
  inserted between separate paste blocks so their edge lines cannot
  accidentally fuse into one Memory.
- Blank and whitespace-only lines are ignored.
- Leading and trailing whitespace is removed from every retained line, exactly
  as with `mem add --input`.
- `F2` and `Ctrl-D` leave capture mode and open an explicit confirmation step.
- `Ctrl-C`, a rejected confirmation, empty input, or an input error makes no
  Context change and creates no checkpoint.
- One accepted paste creates all Memories in order and one automatic
  checkpoint for the operation.
- `INFO`, `--input`, and `--paste` are mutually exclusive input modes.

The command remembers the selected Context identity when capture begins, then
reloads that Context immediately after confirmation. This preserves updates
that another process saved while the paste UI was open. If the Context was
deleted and recreated under the same name, the UID mismatch aborts the
operation rather than writing into a different workspace.

`--paste` requires an interactive terminal. Scripts and pipelines should keep
using `mem add --input FILE` or `... | mem add --input -`; those modes remain
deterministic and do not gain a confirmation prompt.

## Why this is a separate mode

Shell stdin and terminal paste may carry the same bytes, but they express
different intentions. `--input -` is composable automation and should consume
stdin directly. `--paste` is a human review flow: conceal the raw intake,
report its structural size, ask before mutation, and leave a single reversible
checkpoint.

The implementation delegates raw-terminal handling and bracketed-paste parsing
to `prompt_toolkit`. Memcommit owns only the small state machine around it:
capture, count, confirm, parse, and save. This avoids maintaining
platform-specific terminal mode and escape-sequence code in the repository.

## Downstream refinement

Paste intake intentionally does not deduplicate, resolve apparent conflicts,
infer audiences, normalize wording, or choose organizational destinations.
It also does not decide whether a line contains one focal commitment or
several. Those decisions belong to separate, reviewable operations described
in the
[memory refinement pipeline](memory-refinement-pipeline-design-rationale.md)
and the [`mem atomize` design](mem-atomize-design-rationale.md).

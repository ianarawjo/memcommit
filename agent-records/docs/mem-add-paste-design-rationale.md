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

This is a concealed display boundary, not an access-control boundary. Finishing
capture with `F2` or `Ctrl-D` is the complete approval to store the full text
in the Context and its checkpoint like any other Memory. Later commands may
display it.

## Command contract

```console
$ mem add --paste
Paste text; each non-empty line becomes one Memory.
[0 lines pasted]  F2/Ctrl-D: add  Esc/Ctrl-C: cancel

[12 lines pasted]
Added 12 Memories to 'temp/task-1'.
```

- A bracketed paste is captured without echoing its text.
- Multiple paste events are appended in arrival order. A missing newline is
  inserted between separate paste blocks so their edge lines cannot
  accidentally fuse into one Memory.
- Blank and whitespace-only lines are ignored.
- Leading and trailing whitespace is removed from every retained line, exactly
  as with `mem add --input`.
- `F2` and `Ctrl-D` finish capture and immediately commit the exact parsed
  batch; `--paste` plus that finish key are the explicit mutation request.
- `Escape`, `Ctrl-C`, empty input, or an input error makes no Context change
  and creates no checkpoint.
- One finished paste creates all Memories in order and one automatic
  checkpoint for the operation.
- That checkpoint retains the parser/mode, ordered created Memory UIDs, exact
  raw intake text, and its SHA-256 value. `mem trace` can therefore recover a
  Memory's item ordinal and physical source line without adding fields to the
  minimal `{uid, content}` Memory record.
- `INFO`, `--input`, and `--paste` are mutually exclusive input modes.

The command remembers the selected Context identity when capture begins, then
reloads that Context immediately after capture. This preserves updates
that another process saved while the paste UI was open. If the Context was
deleted and recreated under the same name, the UID mismatch aborts the
operation rather than writing into a different workspace.

`--paste` requires an interactive terminal. Scripts and pipelines should keep
using `mem add --input FILE` or `... | mem add --input -`; those modes remain
deterministic and do not enter the concealed capture surface.

Trace labels a new source occurrence `RECORDED` only when the raw-text hash and
ordered UID ledger verify. If either has been damaged, it reports reconstructed
order instead of claiming exact raw provenance. Older checkpoints without this
metadata remain readable but cannot retroactively prove the original bytes.

## Why this is a separate mode

Shell stdin and terminal paste may carry the same bytes, but they express
different intentions. `--input -` is composable automation and should consume
stdin directly. `--paste` is a human intake flow: conceal the raw input,
report its structural size, commit only when the person presses the dedicated
finish key, and leave a single reversible checkpoint. A second `y/N` would
repeat intent already expressed by the explicit mode and finish action.

The implementation delegates raw-terminal handling and bracketed-paste parsing
to `prompt_toolkit`. Memcommit owns only the small state machine around it:
capture, count, finish, parse, and save. This avoids maintaining
platform-specific terminal mode and escape-sequence code in the repository.
Escape and Ctrl-C both cancel capture without returning any concealed payload;
F2 or Ctrl-D remains the only path that returns the batch for Add.

The terminal capture component is owned by
`memcommit.adapters.console.terminal.components.paste_input`. The historical
`memcommit.adapters.console.coordination.paste_input` facade is removed, so imports
and monkeypatches target the canonical component directly. This is an
ownership-only relocation: key bindings,
paste normalization, TTY checks, cancellation and failure behavior, and the
no-payload-echo boundary are unchanged.

The source contract and record grammars have different owners. The shared
UTF-8 file/stdin reader lives in
`memcommit.adapters.console.coordination.batch_input_source`; Add's stripped,
non-empty line grammar lives in `commands.add.line_input_records`, and Edit's
first-tab grammar lives in `commands.edit.input_records`. The former
`interfaces.cli.batch_input` owner and intermediate `console.shared.batch_input`
facade are removed rather than retained as internal compatibility paths. This
separation does not change newline preservation, UTF-8 or I/O failure handling,
Add line stripping, or Edit's first-tab/content-preservation behavior.

### Relationship to `mem ls --paste`

`--paste` is intentionally command-local rather than one hidden global input
mode. `mem add --paste` continues to mean interactive bracketed-paste capture:
the person enters text in a concealed TTY surface and finishes that surface to
commit a Context mutation. By contrast, `mem ls --paste` reads and displays
the frozen structured list snapshot previously created by `mem ls --copy`; it
does not capture terminal input or mutate a Context.

These forms share the user-level idea of consuming pasted material, but not
the same source contract. A future generic clipboard protocol must reconcile
that distinction explicitly instead of silently changing the established Add
intake behavior.

## Downstream refinement

Paste intake intentionally does not deduplicate, resolve apparent conflicts,
infer audiences, normalize wording, or choose organizational destinations.
It also does not decide whether a line contains one focal commitment or
several. Those decisions belong to separate, reviewable operations described
in the
[memory refinement pipeline](memory-refinement-pipeline-design-rationale.md)
and the [`mem atomize` design](mem-atomize-design-rationale.md).

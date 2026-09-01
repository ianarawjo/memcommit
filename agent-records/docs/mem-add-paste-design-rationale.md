# `mem add --paste` design rationale

## Motivating problem

The earlier `mem add --paste` opened a concealed prompt-toolkit intake
surface. A person still had to paste manually and then press `F2` or
`Ctrl-D`, even though the option name suggested that Add would consume the
clipboard directly. Its line counter and second persistent count also added a
review ceremony that did not change how the batch was parsed or stored.

`--paste` now means one explicit, immediate read from the system clipboard.
List's former structured `--paste` replay was removed separately; Add owns the
raw text intake meaning of this option.

## Command contract

`mem add --paste` reads the exact clipboard text through
`memcommit.adapters.console.clipboard.read_system_clipboard`. The current
adapter invokes dependency-free `/usr/bin/pbpaste` on macOS, rejects process
failure and non-UTF-8 output, and reports unsupported platforms through
`ClipboardError`.

The command then applies the same Add-owned physical-line grammar as
`mem add --input`:

- every non-empty physical line becomes one Memory;
- leading and trailing whitespace is stripped from each retained line;
- blank or whitespace-only clipboard text fails before target mutation;
- all retained Memories are appended in order through one `AddRequest`, one
  authorized save, and one automatic checkpoint; and
- `INFO`, `--memory`, `--input`, and `--paste` remain mutually exclusive
  intake choices.

There is no paste screen, line-count preamble, finish key, cancellation state,
or second confirmation. Supplying `--paste` is the complete request to read
and add the clipboard text. After the save, the ordinary Add receipt uses the
same complete form as every other intake: resulting count and Target, every
created Memory UID/content pair in order, and the checkpoint. Clipboard intake
does not create a separate privacy or presentation mode.

## Provenance and mutation boundary

Clipboard intake retains `mode="PASTE"` so existing Add checkpoint and trace
readers continue to recognize the CLI route. New checkpoints record
`kind="system-clipboard"`, the exact raw UTF-8 text, the shared line-parser
identifier, its SHA-256 digest, ordered contents, and created Memory UIDs.
This distinguishes clipboard provenance from file/stdin provenance without
giving it different Memory or checkpoint materialization semantics.

The command captures the current Context name once before reading the
clipboard, so a relative target keeps one meaning. Unlike the retired
long-lived interactive surface, clipboard intake does not pre-freeze a target
UID before the read. Target authority and identity are resolved through the
normal `run_add` boundary after the clipboard has been read, just as they are
for file input. The Store adapter still rejects replacement after a target has
actually been frozen and before it is saved.

## Alternatives and limitations

Renaming the option to `--clipboard` was considered. Keeping `--paste` avoids
a compatibility break and now makes its behavior more literal: the command
pastes from the clipboard instead of asking the terminal to capture a future
paste. It does not imply a paired List operation: `mem ls --copy` produces
plain text, while only Add interprets clipboard text as new Memories.

Routing this behavior through `mem import` was rejected. Import preserves
existing memcommit Profile, Context, or Memory identity from another managed
source; clipboard text creates new Memories and therefore remains Add input.

The shared clipboard adapter is currently macOS-only. Clipboard text is not
deduplicated, semantically split, normalized beyond physical-line stripping,
or reviewed before storage. Those transformations remain separate,
reviewable operations. The retired
`memcommit.adapters.console.terminal.components.paste_input` component is
removed because no command owns its bracketed-paste state machine anymore.

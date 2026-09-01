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

The command passes that text to Add's application-owned physical-line grammar:

- every non-empty physical line becomes one Memory;
- leading and trailing whitespace is stripped from each retained line;
- blank or whitespace-only clipboard text fails before target mutation;
- all retained Memories are appended in order through one `AddRequest`, one
  authorized save, and one automatic checkpoint; and
- positional `MEMORY...` values and `--paste` remain mutually exclusive intake
  choices.

There is no paste screen, line-count preamble, finish key, cancellation state,
or second confirmation. Supplying `--paste` is the complete request to read
and add the clipboard text. After the save, the ordinary Add receipt uses the
same complete form as every other intake: resulting count and Target, every
created Memory UID/content pair in order, and the checkpoint. Clipboard intake
does not create a separate privacy or presentation mode.

## Checkpoint and mutation boundary

Clipboard intake becomes the same ordered `contents` value as every other Add
route before the application runs. New Add checkpoints record the normalized
contents, their created Memory UIDs, and the count, but not whether the adapter
received them from argv, the clipboard, the TUI, or the Python API. Trace can
therefore establish that Add created each Memory without presenting the input
transport as semantic lineage. Existing checkpoints that contain the retired
source record remain readable and may still expose their historical raw-source
detail.

This boundary is intentionally narrower than Embed or Import provenance. Those
operations identify an upstream Context or Memory and must retain its UID and
digest. Clipboard text has no such durable source identity; storing its raw
text and hash beside the resulting contents duplicated input mechanics without
establishing a resource lineage.

The command captures the current Context name once before reading the
clipboard, so a relative target keeps one meaning. Unlike the retired
long-lived interactive surface, clipboard intake does not pre-freeze a target
UID before the read. Target authority and identity are resolved through the
normal `run_add` boundary after the clipboard has been read. The Store adapter
still rejects replacement after a target has actually been frozen and before
it is saved.

## Alternatives and limitations

Renaming the option to `--clipboard` was considered. Keeping `--paste` avoids
a compatibility break and now makes its behavior more literal: the command
pastes from the clipboard instead of asking the terminal to capture a future
paste. It does not imply a paired List operation: `mem ls --copy` produces
plain text, while only Add interprets clipboard text as new Memories.

Routing clipboard behavior through `mem import` was rejected. Clipboard text
is a direct user-selected Add source, while files, arbitrary documents, and
Skills belong to Import's intentionally `PARTIAL` resource surface. Import may
create new Memories through the Add application after interpreting such a
resource; it does not own the platform clipboard action.

The shared clipboard adapter is currently macOS-only. Clipboard text is not
deduplicated, semantically split, normalized beyond physical-line stripping,
or reviewed before storage. Those transformations remain separate,
reviewable operations. The retired
`memcommit.adapters.console.terminal.components.paste_input` component is
removed because no command owns its bracketed-paste state machine anymore.

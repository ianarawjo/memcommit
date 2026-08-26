# `mem help` common locators and controls

This ordered set records the shared locator grammar and the actual keyboard
controls shown by interactive `mem help`. Every interactive state comes from
the installed `mem` executable in a real `180×52` color PTY with
`TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed. Help is
Store-free and read-only, so no Profile or current Context is loaded or changed.

`COMMON LOCATORS` distinguishes canonical global bare Context names from `.`,
`..`, `./CHILD`, and `../PATH`. It also explains unique bare direct-Memory UID
or prefix discovery and the explicit `CONTEXT:UID` owner form, including the
relative `../3:ca562047` example. `COMMON KEYS` is checked against the Help browser's
bindings: vertical and horizontal arrows, PageUp/PageDown, Home/End,
Tab/Shift-Tab, Enter, H, Escape, Q, and Ctrl-C. Backspace is not advertised
because this Help browser does not bind it.

## Ordered interaction log

| Capture | Exact command and preceding input | Visible state | Durable mutation |
|---|---|---|---|
| `01-common-locators-and-keys` | `mem help`; none | English `COMMON LOCATORS` and `COMMON KEYS` entry guide | none |
| `02-view-arrow-focus` | same process; `Shift-Tab` | focused View control and its `←/→` footer guidance | none |
| `03-korean-locator-and-key-guide` | same process; `Shift-Tab`, `Right` ×3 | Korean locator and key guidance with exact syntax retained | none |
| `04-embed-qualified-locator-form` | fresh `mem help`; `Tab`, `Down` ×5, `Right`, `Down` ×2 | canonical unique-UID and `CONTEXT:UID` Embed Forms | none |
| `05-embed-from-compatibility-form` | same process; `Down` ×4 | `--from` retained and labelled as compatibility syntax | none |
| `06-reference-qualified-locator-form` | fresh `mem help`; `Tab`, `Down` ×4, `Right`, `Down` ×2 | canonical unique-UID and `CONTEXT:UID` Reference Forms | none |
| `07-edit-qualified-locator-form` | fresh `mem help`; `Tab` ×3, `Right` | Edit's canonical `UID_or_CONTEXT:UID` Form | none |
| `08-plain-read-only-verification` | `mem help </dev/null` filtered to Edit, Embed, and Reference | deterministic non-TTY inventory after every interactive process closed | none |

Each stem has the raw color-preserving PTY stream (`.typescript`), the rendered
terminal text (`.txt`), and a full-canvas PNG (`.png`). Run
`python agent-records/screenshots/mem-help-common-locators-controls-20260821/capture.py`
from the repository root to refresh the complete set.

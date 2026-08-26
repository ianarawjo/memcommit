# `mem provider` read-only entry evidence

Refreshed on 2026-08-23 from the real repository commands in color-capable
`180×52` PTYs with `TERM=xterm-256color`, `COLORTERM=truecolor`, and
`NO_COLOR` removed. Every child verifies its live terminal dimensions before
launching `mem`. The raw PTY stream (`.typescript`), decoded terminal canvas
(`.txt`), and full-resolution rendering (`.png`) are retained for each step.

All runs use temporary isolated HOME directories. They do not read or change
the user's Profile registry, provider routes, configuration, Contexts, or
Memories. Bare Provider and status make no provider connection. The capture
asserts that bare Provider exits by itself without entering an alternate
screen, rendering an Enter prompt, or waiting for input.

## Editable ordinary Profile

The Profile is `authoring`; no Context is opened because Provider routing is
Profile control state rather than Context data.

| Snapshot | Exact command | Visible state | Durable effect at this step |
| --- | --- | --- | --- |
| `01-general-read-only-overview` | `mem provider` | Stable general Profile route overview; the command has already exited and no editor is open | None |
| `02-general-explicit-use-receipt` | `mem provider use ollama --model qwen3.6:35b-a3b --thinking auto` | Explicit route mutation receipt and separate Probe guidance | One Profile route sidecar and its retained Ollama machine setting |
| `03-general-updated-overview` | `mem provider` | Stable overview now reports the authored Ollama default and `profile_default` source; the command exits without input | None |

## Locked Study Profile

The active Profile is `provider-study`; no Context exists or is opened.

| Snapshot | Exact command | Visible state | Durable effect at this step |
| --- | --- | --- | --- |
| `04-study-read-only-overview` | `mem provider` | Complete pinned Study matrix, version, digest, edit lock, and explicit command guidance; the command has already exited | None |
| `05-study-edit-rejected` | `mem provider use ollama --model qwen:latest` | The explicit mutation command fails closed because Study routing is fixed | None; no route sidecar is written |
| `06-study-read-only-verification` | `mem provider status`, then filesystem sidecar count | Effective route remains pinned Codex and Profile route sidecar count is exactly zero | None; status and sidecar inspection are read-only |

The capture script also asserts foreground ANSI styling on explicit receipts
and failures, absence of recorder-only CPR warnings, absence of alternate-
screen control sequences across bare Provider captures, successful ordinary
route publication, Study rejection, and zero partial Study route publication.

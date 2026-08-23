# `mem provider` Profile-routing interaction evidence

Captured on 2026-08-23 from the real repository command in color-capable
`180×52` PTYs with `TERM=xterm-256color`, `COLORTERM=truecolor`, and
`NO_COLOR` removed. Every child verifies its live terminal dimensions before
launching `mem`. The raw PTY stream (`.typescript`), decoded terminal canvas
(`.txt`), and full-resolution rendering (`.png`) are retained for each step.

All runs use temporary isolated HOME directories. They do not read or change
the user's Profile registry, provider routes, configuration, Contexts, or
Memories. Provider setup and status make no provider connection; the Study
Probe control is visible but is not activated in this evidence set.

## Editable ordinary Profile

The Profile is `authoring`; no Context is opened because Provider routing is
Profile control state rather than Context data.

| Snapshot | Exact command or preceding input | Visible state | Durable effect at this step |
| --- | --- | --- | --- |
| `01-general-entry` | `mem provider` | General editable screen; Codex is the inherited default, effective routes are visible, and contact status is `NOT CONTACTED` | None |
| `02-general-ollama-selected` | `Down` | Shared checked-row selection stages Ollama; the required Model field is still empty | None |
| `03-general-model-entered` | `Enter`, type `qwen3.6:35b-a3b` | Exact Ollama model text is process-local; no route has been written | None |
| `04-general-exact-command-review` | `Enter`, `Enter` | To Do shows `mem provider use ollama --model qwen3.6:35b-a3b --thinking auto`, complete effects, and the final Apply gesture | None |
| `05-general-apply-receipt` | `Enter` | The reviewed route is written for Profile `authoring`; the receipt points to the separate Probe action | One Profile route sidecar and its retained Ollama machine setting |
| `06-general-read-only-status` | `mem provider status` | Effective provider is Ollama, model is `qwen3.6:35b-a3b`, and source is `profile_default` | None; status is provider-free and read-only |

## Locked Study Profile

The active Profile is `provider-study`; no Context exists or is opened.

| Snapshot | Exact command or preceding input | Visible state | Durable effect at this step |
| --- | --- | --- | --- |
| `07-study-locked-entry` | `mem provider` | Complete pinned Study matrix, version, digest, edit lock, Profile-switch guidance, and explicit default Probe action | None |
| `08-study-edit-rejected` | `mem provider use ollama --model qwen:latest` | The ordinary mutation command fails closed because Study routing is fixed | None; no route sidecar is written |
| `09-study-read-only-verification` | `mem provider status`, then filesystem sidecar count | Effective route remains pinned Codex and Profile route sidecar count is exactly zero | None; status and sidecar inspection are read-only |

The capture script asserts the PTY dimensions, foreground and background ANSI
styles, absence of recorder-only CPR warnings, exact reviewed command,
successful ordinary route receipt, effective status, Study rejection, and
zero partial Study route publication.

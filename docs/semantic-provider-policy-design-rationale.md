# Profile provider routing design rationale

## Motivation

Semantic provider selection used to mix two different requirements. Ordinary
work needed a convenient, editable provider/model/reasoning combination, while
a Study run needed the exact experimental condition to remain reproducible.
The earlier global configuration plus operation-pin model did neither cleanly:
all Profiles shared one mutable default, yet a person could not tell from that
configuration which hard-coded operation exceptions would replace it.

The user-visible symptom was output such as `rule: pinned identity`. That
described an implementation rule rather than answering the useful questions:
which Profile owns this route, can it be changed, and what will this operation
actually execute?

## Two configuration modes

Provider routing now has two deliberately asymmetric modes selected from the
active Profile before provider contact.

### General Profiles

An ordinary Profile may own:

- one complete default route; and
- zero or more complete operation routes keyed by semantic operation name.

A route is the provider ID, model, Codex reasoning effort when applicable, and
timeout. An operation route replaces the Profile default as one combination;
unset operations use the default. This avoids half-inherited identities such
as a model from one provider combined with reasoning intended for another.

The editable document is stored under
`~/.mem-profiles/provider-routes/<profile-uid>.json`. It is keyed by immutable
Profile UID rather than editable display name and repeats that UID inside the
strict schema. Writes use a per-Profile advisory lock, a same-directory
temporary file, `fsync`, and atomic replacement. Provider routes are control
state, not Memory: they do not enter the Profile store, export, grant, or
Context namespace.

For migration, an ordinary Profile without a route document inherits the old
machine default in `~/.mem/config.json`. The first `mem provider use` writes a
Profile route without rewriting that legacy identity. Endpoint, credential,
context-window, output-budget, thinking, and zero-data-retention settings
remain machine-local transport configuration because they describe the local
runtime rather than a portable Profile identity.

### Study Profiles

A Study Profile has no editable route document. `mem init-study` records both
the Study provider-configuration version and its canonical SHA-256 digest in
the participant and granted-memory Profile provenance as part of the same
registry publication transaction. Runtime resolution loads the named
version from code and verifies the digest before provider contact.

The first version, `study-provider-config-v1`, contains this complete matrix:

| Route | Provider | Model | Reasoning | Timeout |
| --- | --- | --- | --- | ---: |
| default | `codex_chatgpt` | `gpt-5.6-sol` | `none` | 600 s |
| `search` | `codex_chatgpt` | `gpt-5.6-terra` | `low` | 600 s |
| `query` | `codex_chatgpt` | `gpt-5.6-sol` | `none` | 600 s |
| `help` | `codex_chatgpt` | `gpt-5.6-sol` | `none` | 600 s |
| `forget` | `codex_chatgpt` | `gpt-5.6-sol` | `none` | 600 s |
| `compare_contexts` | `codex_chatgpt` | `gpt-5.6-sol` | `none` | 900 s |
| `meld_contexts` | `codex_chatgpt` | `gpt-5.6-sol` | `none` | 900 s |

Future Study changes add a new retained version rather than mutate this
matrix. Existing Study Profiles therefore continue to name their original
configuration. A Study Profile created before provider pinning, an unknown
version, or a digest mismatch fails closed before semantic execution; silently
substituting the newest condition would make the run look reproducible when it
is not. Recreating the run through `mem init-study` is the explicit migration.

## Runtime and CLI contract

Each ordinary semantic command freezes the active Profile and its route once,
then connects the resolved provider. Find, ordinary Query, Help, Forget, and
the shared completion factory all use this boundary. Explicit evaluation
arguments and authorized query-only source routes remain separate: they must
not rewrite Profile configuration or be silently rerouted by it.

Bare `mem provider` is a provider-free inspection of the active Profile. A
general Profile is labelled `general · editable` and shows its effective
default plus only the operation routes the person configured. A Study Profile
is labelled `study · locked` and shows the pinned version, digest, and complete
Study matrix. The output intentionally contains no `rule` or “fixed by
operation” explanation; editability and ownership are first-class fields.

`mem provider use PROVIDER` edits the active general Profile default.
`--operation OPERATION` edits one operation combination. `mem provider reset`
removes the Profile default and returns it to the legacy machine fallback;
with `--operation`, it removes just that operation route. Both commands reject
a Study Profile. `status` resolves one route without contact, and `probe`
connects that exact active-Profile route for one synthetic strict-schema call.

Resolved receipts retain the general policy version, configuration version
when Study-owned, route source, full effective values, and digest. The digest
distinguishes resolution receipts; the Study provenance digest separately
protects the complete versioned matrix.

## Evaluation and prewarm boundary

`EVALUATION` remains the only mode that accepts a process-local provider
override. Evaluation campaigns may select another model or reasoning tier
without changing any Profile. Study prewarm generation selects the current
Study configuration while constructing a new run; `init-study` then pins that
version and digest. Participant runtime resolves the pin rather than a mutable
machine default.

Timeout is an independent route axis. A 900-second Study route for deep Compare
or Meld does not increase semantic input budgets, authorize prompt splitting,
or change the operation's validation and application boundary.

## Alternatives and limitations

Keeping every route in one global config was rejected because switching
Profiles would not switch execution conditions. Keeping general operation
routes hard-coded was rejected because normal, non-Study work is explicitly
meant to compose provider/model/reasoning choices. Copying editable routes into
Study stores was rejected because a participant could then alter or export the
experimental condition as if it were Memory.

The compatibility machine default remains only as an unset-general-Profile
migration fallback; it is not consulted by a pinned Study route. Removing a
Profile does not yet garbage-collect its UID-keyed provider sidecar. That file
is unreachable from a new Profile identity and contains configuration rather
than Memory, but a later Profile-removal cleanup may delete it under the same
registry transaction boundary.

This layer does not choose execution strategy, prompt size, schema, retry, or
batching. Those remain operation contracts under `memcommit.semantic_execution`.

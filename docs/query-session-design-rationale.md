# Query one-shot retention rationale

Last verified: 2026-08-22.

## Decision

Query is one-shot across the CLI, TUI, Python API, and agent adapter. It does
not create, append, list, reopen, or search saved transcripts. The earlier
named Query-session experiment and its `SESSION_LOG` capability have been
removed.

The result remains visible only in the active process and in stdout or an
explicit user clipboard copy. `mem query` has no `--session`, `--sessions`, or
`--show-session` forms, and its workbench has no Session Name, Saved
Transcripts, or To Do frame.

This makes the interactive surface match the direct CLI contract: each Enter
freezes one Source selection and one question, performs one provider turn,
shows one answer, and retains no memcommit-owned history after the process
closes.

## Compatibility boundary

Older Profile registries can contain `SESSION_LOG`. Registry loading
normalizes that retired permission to `QUERY` so an existing Profile does not
become unusable, but no retention authority or storage behavior is restored.
New grants cannot request `SESSION_LOG`, and capability displays expose only
`QUERY`.

Existing files under a legacy `query-sessions/` directory are deliberately not
deleted. Destructive migration is outside Query execution. Current code does
not read, replay, index, append, or otherwise publish those records. Clean
Profile import continues to exclude the directory.

## Source and provider invariants

- Ordinary Query freezes exact readable Context targets through the shared
  readable catalog before constructing its request.
- Query-only discovery uses public grant routing metadata; concealed authority
  Source content opens only after provider construction succeeds.
- A granted answer is withheld if its grant or Source binding changes while
  the provider is running.
- Relevant-descendant federation receives public names only and opens only the
  authorized subset selected for that one request.
- Opaque Memory handles and Flow Circular placeholders remain process-local
  projections and are never written to the grantee Store.
- Search artifacts contain retained workflow evidence from operations that
  actually own durable review state; Query answers are not indexed.

## Why the session experiment was removed

Saved transcripts made the TUI materially more complex than the direct CLI:
Source selection was mixed with a Session Name field, a persistent transcript
browser, replay behavior, CAS publication, and a second authority capability.
That complexity did not support an Apply or resumable-review boundary. Unlike
Compare, Meld, Update, or Sever, Query has no reviewed proposal whose later
materialization depends on retaining the operation artifact.

A one-shot answer is also the clearer privacy contract. `QUERY` authorizes the
current provider-mediated disclosure; it no longer implicitly starts a new
task-owned retention lifecycle. Users who intentionally need a copy still
control stdout redirection or the explicit plain-text clipboard action.

## Alternatives considered

- **Keep sessions only in the TUI:** rejected because it gives identical Query
  requests different retention semantics depending on terminal adapter.
- **Keep an optional CLI flag:** rejected because the storage, authority,
  replay, and migration contracts remain even if the control is visually
  hidden.
- **Automatically delete legacy records:** rejected because feature removal
  does not authorize destructive cleanup of user data.
- **Use provider-side conversation state:** rejected because it would retain
  unauditable state outside the local one-shot contract.
- **Reuse saved-session workbenches from review operations:** rejected because
  Query has no deferred Apply or required resolution that justifies one.

## Limitations

One-shot means follow-up questions are independent calls; the user must include
the necessary context in each question. The provider can still answer too
broadly, and this research prototype does not provide OS-level confidentiality.
Legacy transcript files may remain on disk until the user chooses a separate,
explicit cleanup policy.

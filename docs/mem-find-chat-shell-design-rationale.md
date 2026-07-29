# Find chat shell staging rationale

## Problem

The shared Ground TUI assets are still being developed, while `mem find`
eventually needs a conversational surface for queries whose useful result set
is not known in advance. Directly copying Ground's Goal--Rules--Cases shell
would couple Find to Ground-specific provider responses, approval semantics,
and persistence. Wiring an unfinished search session into the existing
`mem find` command would also change its stable plain-output contract before
selection and materialization have been designed.

## Staged decision

`find_chat_shell.py` imports only the operation-neutral terminal assets:

- vertical TUI regions and frame composition;
- interactive-terminal validation;
- terminal-safe text; and
- viewport anchoring.

It presents a controller-supplied header and transcript, collects one nonblank
user turn, returns a typed `SUBMIT` or `CLOSE` action, and exits. It does not:

- call the semantic provider;
- search a Context;
- own result or kept-item identity;
- persist dialogue or a Find session;
- copy to the clipboard;
- create a Context or checkpoint; or
- alter the current `mem find` CLI behavior.

The one-action boundary is intentional. A later Find controller can call the
provider outside prompt-toolkit's key handler, update a separately designed
`FindSession`, and reopen the shell with the resulting transcript and counts.
This avoids inheriting Ground's current synchronous-provider repaint
limitation and lets shared TUI internals change without making Find depend on
Ground domain classes.

## Integration boundary

The waiting shell becomes user-facing only after a controller can supply:

1. locally validated search results and their stable source identities;
2. explicit current-result and kept-item state;
3. stale-source detection for any result that may later be materialized; and
4. a separate exact-command approval for the final state-changing operation.

Until then, the existing grouped `mem find` output remains authoritative.
`ExactCommandReview` is deliberately not used by the chat shell because
submitting a query is read-only. It belongs at the later materialization
boundary, where kept results are turned into a new Context through a normal
CLI command.

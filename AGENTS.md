# Repository agent instructions

## Running `mem` commands

- When the user enters a `mem` command, such as `mem ls`, run the command from
  this repository's root and report its actual output instead of only
  describing what it would do.
- Use the repository root as the default working directory; `cd` or `pwd` is
  only needed when the user explicitly requests it or the working directory
  must be diagnosed.
- If the `mem` executable is not available on `PATH`, run the equivalent
  project entry point with `python -m memcommit.cli ...` and clearly identify
  that fallback.

## Preserving design intent

This repository is a research prototype, and its implementation history may be
used later to reconstruct design decisions and write study materials. Treat
the rationale as part of the deliverable rather than leaving it only in the
conversation.

- Every commit created by an agent must explain both **what changed** and
  **why**. Use the subject for a concise outcome and the commit body for the
  problem or context, intended behavior, and reason for the chosen approach.
  Do not merely restate the diff.
- When relevant, record the important tradeoff, rejected alternative, safety
  or compatibility boundary, and intentional non-goal. Keep the account
  concise and factual; do not invent retrospective certainty.
- For a material or non-obvious design decision, create or update a focused
  note under `docs/`, normally named `*-design-rationale.md`. Preserve the
  motivating scenario, command or data contract, invariants, alternatives
  considered, and limitations that may matter to a later implementation or
  research write-up.
- Put short comments next to non-obvious invariants, concurrency decisions,
  privacy boundaries, workarounds, and deliberately asymmetric behavior in the
  code. Comments should explain **why the code must behave this way**, not
  narrate mechanics that are already obvious from the code.
- Keep the implementation, tests, rationale note, and commit body consistent.
  If later work changes the behavior or invalidates an earlier reason, update
  the existing note in the same change instead of leaving a misleading design
  history.
- Before committing, check that a future reader can answer: What problem did
  this solve? What behavior was intended? Why was this design selected? What
  boundary or limitation remains?

## Query-only research prototype

- When the user enters `mem query`, run that command and report its actual
  response. Do not replace it with an independently composed answer.
- Never open `~/.mem/query-sources/` to answer a user query or expose its raw
  contents through another command. Access query-only content only through
  `mem query`; `mem find` may search a query-only Context's public name only.
- The current provider is a temporary, one-shot Codex session authenticated
  with the local user's ChatGPT login. This is a research simulation intended
  to be replaced by MCP or an internal-network provider later.

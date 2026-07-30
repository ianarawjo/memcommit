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

## Agent-mediated Ground turns

When the user is working from a target-focused screen such as
`mem ground NAME --focus-target TARGET`, treat the CLI as the execution
boundary and the agent as the conversational orchestrator.

- In a TTY, `mem ground` without arguments opens the provider-backed blank
  Ground TUI. Outside a TTY it prints the same stable unsaved frame and exits.
  The TUI may propose a Goal and portable name, but it must not create the
  named Ground until the user presses the dedicated approval key for the exact
  displayed command. Ground has no separate completion criterion: closing a
  view is not agreement, and any future whole-Ground agreement must require
  explicit approval of one reviewed Goal–Rules–Cases revision.
- The blank TUI sends only the person's submitted dialogue text to the
  provider. It must not infer, load, or transmit the current Context,
  query-only sources, or existing Ground data.
- After an approved creation, continue in the named-Ground TUI. An unbound
  Ground must obtain a separately approved explicit frame-binding command
  before proposing Rules or Cases; never infer binding from the current
  directory or current Context.
- A named-Ground semantic turn may send the saved Goal, Rules, Cases, local
  item aliases, revision, and bound Context names to the provider. It must not
  load or send live Context projections, durable UIDs, query-only material, or
  host-constructed executable command text. A saved Case's content may be an
  earlier copy of source Memory text, but its source identity remains local.
  Its current unresolved dialogue may include the provider's own
  previously displayed understanding and question so short follow-up answers
  retain their visible referent; do not rely on hidden provider session state.
  Case source selectors are resolved locally after the person supplies them,
  replaced with stable local aliases before inference, and mapped back only
  when the provider returns an alias that was actually introduced.
- Recording a `PROPOSED` Rule or Case and accepting it are distinct Ground
  commands and require distinct approvals.
- Commands proven to be read-only, including focus rendering of an existing
  Ground, do not require a separate approval. Confirm that a named Ground
  exists before treating `--snapshot` as read-only because the legacy
  create-or-resume form creates a missing Ground.
- Translate one user response into at most one state-changing `mem` command.
- Before running that command, show its exact arguments and explain which one
  of Goal, Rules, or Cases it will change. Display-escape layout and bidi
  controls so untrusted argument or effect text cannot imitate another command
  or trusted heading. Approval binds the frozen raw argv represented by this
  receipt; the escaped display is not a copy-paste shell command.
- Preserve the exact command's Ground-version precondition. Interactive
  mutations must reach the normal CLI save boundary with the reviewed Ground
  UID, revision, and digest, and bound Context frames must be rechecked under
  their write locks; a UI-only freshness check is not sufficient.
- Wait for explicit user approval. Approval applies only to the displayed
  command; it does not authorize a follow-up command.
- After approval, run exactly that command through the normal CLI path and
  report its actual output. Ask separately before proposing or running another
  state-changing command.
- Never implement a Ground turn by directly editing a Ground JSON file or a
  Context. Ground changes must use `mem ground`; Context changes must use the
  corresponding `mem` operation so their validation, provenance, and
  checkpoint boundaries remain authoritative.
- This protocol governs user-directed Ground interaction. It does not turn
  read-only diagnostics or repository implementation work that the user
  explicitly requested into one-command approval prompts.

## Query-only research prototype

- When the user enters `mem query`, run that command and report its actual
  response. Do not replace it with an independently composed answer.
- Never open `~/.mem/query-sources/` to answer a user query or expose its raw
  contents through another command. Access query-only content only through
  `mem query`; `mem find` may search a query-only Context's public name only.
- The current provider is a temporary, one-shot Codex session authenticated
  with the local user's ChatGPT login. This is a research simulation intended
  to be replaced by MCP or an internal-network provider later.

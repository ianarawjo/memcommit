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

## Existing Context locators

- When adding or updating a CLI operand whose semantic role is to locate an
  existing ordinary Context, use
  `memcommit.context_locator.resolve_context_locator` instead of adding
  command-local `.` or `..` parsing.
- Capture the active Context name once at command start and resolve every
  relative operand against that same snapshot. Bare names remain canonical
  global names; only `.`, `..`, `./...`, and `../...` opt into relative
  lookup.
- Use the resolved canonical name for existence checks, loading, equality,
  cache/session identity, persistence, and user-visible target confirmation.
  Keep operation-specific load modes, locks, UID/digest checks, and CAS
  boundaries in the calling command.
- Do not apply the existing-Context resolver to new Context identifiers such
  as `init`, `branch`, `checkout -b`, or `--save-as`, or to Memory selectors,
  query-only selectors, provider output, or already persisted names.
- Treat mutating commands and Ground exact-command receipts as a separate
  rollout: display and freeze the canonical target before approval so a raw
  relative locator cannot change meaning with global current state.
- Keep the implementation and rollout list consistent with
  `docs/context-locator-design-rationale.md`.

## Agent-mediated Ground turns

When the user is working from a target-focused screen such as
`mem ground NAME --focus-target TARGET`, treat the CLI as the execution
boundary and the agent as the conversational orchestrator.

- In a TTY, `mem ground` without arguments opens the provider-backed blank
  Ground TUI. Outside a TTY it prints the same stable unsaved frame and exits.
  A natural-language starting request is already the person's first submitted
  turn: do not copy it into the Message composer or wait for a redundant
  Enter. The TUI may propose a Goal and portable name, but it must not create
  the named Ground until the user presses the dedicated approval key for the
  exact displayed command. Ground has no separate completion criterion:
  closing a view is not agreement, and any future whole-Ground agreement must
  require explicit approval of one reviewed Goal–Rules–Memories revision.
- Keep every newly created or revised durable Goal to 40 whitespace-delimited
  words or fewer. A raw starting request may be longer because it is dialogue,
  not yet a saved Goal. When the request already states a clear outcome within
  the limit, preserve it as the proposed Goal; distill only when clarity or the
  limit requires it.
- Before its first provider response, the blank TUI may discover ordinary
  Context locator names from storage paths without opening `context.json`.
  It may send a bounded alias/name catalog with the submitted dialogue so the
  provider can return exactly one name-based `MAIN?` recommendation and up to
  three `ALTERNATIVE` candidates. These are neither validated Contexts nor
  selections. The provider may separately suggest at most one fresh ordinary
  Context name, rendered after alternatives as `NEW? · NAME · NOT CREATED`.
  `Up` and `Down` may focus that row, and `N` opens a process-local exact
  name editor prefilled with the suggestion; submitting it unchanged accepts
  that name as the local plan. A separate
  `ADD NEW CONTEXT · N to enter an exact Context name` row is always available
  after discovery, even when both the catalog and provider suggestion are
  empty, and opens the same editor
  blank initially, then prefilled with the current local plan when reopened,
  so the person can supply or revise a namespaced name such as
  `test/ground/ticker-rule-examples` even when the provider's suggestion is
  poor or absent. The exact name field is one line; suppress `Ctrl-J` there and
  retain multiline input only in `COMMENT (FOR THE AGENT)`. These rows are not
  catalog aliases or checkboxes. The
  suggested, edited, or directly entered name must remain visibly
  `NOT CREATED` and must not enter selected Context hints, Ground JSON, Ground
  creation argv, or binding state. Creating it later requires a separately
  reviewed exact `mem init`, followed by a separately reviewed binding
  command. The shell may separately snapshot and display the local current
  Context name from `state.json`, but that global pointer is orientation only:
  do not tell the provider which catalog name is current, infer a binding from
  it, or open its `context.json`. The blank TUI may auto-focus these frozen
  existing candidates and let the person toggle one or more name-only
  selections. Selection order makes the first checked existing name the local
  Main and later names additional hints. Finishing the picker collapses it to
  selected existing names plus any separate `NOT CREATED` name plan. This
  state must not load or validate an existing Context, switch to one, transmit
  it, or persist it; validating a proposed new name's syntax and read-only
  creatability does not create or bind it. Existing selections may continue
  process-locally into the newly created named-Ground view as visible
  `NOT BOUND` hints, while a new-name plan remains separately `NOT CREATED`.
  When there is no existing candidate, render an explicit
  `CONTINUE WITHOUT CONTEXT PLAN` row so an unaccepted `NEW?` cannot gate
  Ground creation. If a no-candidate proposal has already reached exact
  approval, `N` on its ADD row must first suspend approval mode; restore the
  unchanged receipt only after local validation or explicit cancellation.
  Neither may enter provider input or Ground JSON. Finishing selection and
  approving Ground creation are separate actions. The creation command
  persists only the reviewed Ground name and Goal, while Context creation and
  actual frame binding still require their own exact commands and approvals.
  Do not transmit Context UIDs, Memory content, the active/current Context
  marker, query-only aliases or routing data, or existing Ground contents.
- The blank provider turn may return bounded process-local Rule and Ground
  Memory previews for material already present in the submitted dialogue or
  for clearly marked agent-suggested examples. Render each preview as one
  one-line compact card rather than repeating `DRAFTS · NOT SAVED`, `DRAFT
  RULE/MEMORY`, or rationale rows in the overview. Retain rationale in the
  typed preview for a later detail surface. `USER_EXACT` is displayed as
  `[Provided] [Source-matched]`, while `AGENT_SUGGESTED` is displayed as
  `[Suggested] [Unverified]`. Source matching proves only that the person
  supplied the text, not that the claim is true. Require every displayed
  USER_EXACT Rule content and Ground Memory content/nonempty expected field to
  occur verbatim inside its locally verified source spans; otherwise fail
  closed or classify it as AGENT_SUGGESTED. Agent-suggested Ground
  Memories require no source span, must remain `UNRESOLVED`, and must never be
  presented as user evidence or an authoritative real-world fact. When useful
  examples can clarify the proposed direction, return one to three diverse
  Ground Memory previews; when the person supplied no example, clearly marked
  synthetic previews can provide the first concrete correction target. Prefer
  a fit plus a boundary or contrast when available, and never pad the batch
  merely to reach three. These previews are not part of the Ground creation
  command. A correction replaces the preview batch. Durable promotion still
  requires binding, one exact Rule proposal, one source-traceable Ground
  Memory proposal, and their separate reviews.
- After an approved creation, continue in the named-Ground TUI. An unbound
  Ground must obtain a separately approved explicit frame-binding command
  before proposing durable Rules or Ground Memories; read-only first-turn
  previews do not relax this boundary. Never infer binding from the current
  directory or current Context.
- A named-Ground semantic turn may send the saved Goal, Rules, Ground
  Memories, local item aliases, revision, and bound Context names to the
  provider. It must not load or send live Context projections, durable UIDs,
  query-only material, or host-constructed executable command text. A saved
  Ground Memory's content may be an earlier copy of source Memory text, but
  its source identity remains local.
  Its current unresolved dialogue may include the provider's own
  previously displayed understanding and question so short follow-up answers
  retain their visible referent; do not rely on hidden provider session state.
  Ground Memory source selectors are resolved locally after the person
  supplies them, replaced with stable local aliases before inference, and
  mapped back only when the provider returns an alias that was actually
  introduced. `Memories` is the user-facing Ground layer name; existing
  serialized `kind: "CASE"`, `case_role`, `PROPOSE_CASE`, `cN` aliases, and
  legacy CLI options remain compatibility tokens and must not be migrated
  implicitly. The same applies to `INDUCED_FROM_CASES` and persisted review
  Decision text such as `ACCEPT CASE`: render them with Memory terminology,
  but preserve their stored values for digest and CAS compatibility.
- A long named-Ground comment may produce one read-only `DRAFTS` batch. Split
  it by independent reviewability and classify each unit as Rule, Fact,
  Ground Memory, Goal, or Question; retain exact source spans only after
  verifying that they occur verbatim in the final raw user turn, never merely
  elsewhere in the visible transcript. If local Memory-selector redaction
  changed that source, fail the draft batch closed rather than presenting or
  saving an ephemeral alias as an exact quote. Drafts are process-local and
  not saved Ground items.
  An unbound Ground may preview them, but it must still obtain the separately
  approved frame binding before a selected Rule can become an exact proposal.
  Prepare only the currently selected READY Rule against the latest Ground
  revision; never prebuild commands for the whole queue. Applying it records
  one `PROPOSED` Rule and marks every remaining draft stale. Require a new
  read-only classification against the updated Ground before another draft can
  become READY. A newly submitted user correction or follow-up also marks the
  existing queue stale immediately; only a successful replacement `DRAFTS`
  response may make candidates actionable again.
- Recording a `PROPOSED` Rule or Ground Memory and accepting it are distinct Ground
  commands and require distinct approvals.
- Commands proven to be read-only, including focus rendering of an existing
  Ground, do not require a separate approval. Confirm that a named Ground
  exists before treating `--snapshot` as read-only because the legacy
  create-or-resume form creates a missing Ground.
- Translate one user response into at most one state-changing `mem` command.
- Before running that command, show its exact arguments and explain which one
  of Goal, Rules, or Ground Memories it will change. Display-escape layout and bidi
  controls so untrusted argument or effect text cannot imitate another command
  or trusted heading. Approval binds the frozen raw argv represented by this
  receipt; the escaped display is not a copy-paste shell command.
- Preserve the exact command's Ground-version precondition. Interactive
  mutations must reach the normal CLI save boundary with the reviewed Ground
  UID, revision, and digest, and bound Context frames must be rechecked under
  their write locks; a UI-only freshness check is not sufficient.
- Wait for explicit user approval. Approval applies only to the displayed
  command; it does not authorize a follow-up command.
- While an exact command is pending, `Tab` and `Shift-Tab` may browse the
  read-only Goal, Contexts, Rules, Memories, and Chat panes. The Message
  composer must remain unavailable, and browsing must not alter or imply
  approval of the frozen argv.
- In normal input mode, Chat always contains the general `MESSAGE` composer
  inside its own outer frame. `Enter` on Goal, Contexts, Rules, or Memories
  moves that same buffer into the focused pane and displays it there as
  `COMMENT (FOR THE AGENT)`; `C` is a compatibility alias for the same
  action. The first Escape returns the unchanged general draft to Chat.
  `Enter` on Chat only focuses its already-present general composer and must
  not add a synthetic focus marker. This input is part of the semantic pane,
  not a separately bordered sixth workbench region.
  Pane-local authoring uses the exact labels
  `EDIT (DIRECTLY)` and `COMMENT (FOR THE AGENT)`; do not relabel either one
  as optional. Direct text is an exact replacement constraint and must not be
  rewritten by the provider. A comment-only submission remains an agent turn.
  Use `E` for direct Goal, saved Rule, or saved Memory editing and `R` for a
  READY Rule-draft review. In the blank Context picker, `Space` toggles an
  existing name, `F` finishes or reopens the local plan, and `N` edits a
  proposed or new exact name; `Enter` still opens the Context-focused
  conversation. Do not open any writable surface while exact approval is
  pending.
  Its focused pane supplies the immediate referent, not a semantic scope
  limit: the agent may use that comment to propose a consequential change in
  another Ground layer, subject to the normal one-command and approval
  boundaries. A direct edit remains exact and local to its selected target;
  it does not authorize collateral rewrites. When direct text and a comment
  are submitted together, the comment explains that one local proposal; any
  broader consequence requires a later comment-only turn and approval.
  Goal edits replace the whole Goal, a selected `rN` edit refines only that
  Rule, and a selected `cN` edit refines only the Ground Memory's `expected`
  output; its source text is immutable. Contexts retain their structured
  selection/binding UI and Chat retains the general Message composer.
  In the default `LIST` view, render a Ground Memory as one compact three-line
  Case card: status and classification; `content → expected`; then
  Ground-local `NOTES` (`rationale`, or `(none)`). Fold embedded newlines to a
  visible `↵` without changing stored text. Only the selected Case may expand
  read-only Rule/source/target details. A process-local `TABLE` view may
  present the same Memories as cells; `V` toggles views while MEMORIES is
  focused, `Up`/`Down` move rows, and `Left`/`Right` move columns. The table
  view, row, and column must never enter Ground JSON, provider input, an exact
  command receipt, or binding state. Multiline input or output remains one
  Case when it is one independently reviewable example; never materialize
  Notes into an ordinary Context Memory.
  The first Escape from this expanded editor collapses it without applying or
  closing anything. No pane editor may open while exact approval is pending.
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

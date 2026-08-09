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

## Grant-aware readable Contexts

- Whenever a read or source-selection command promises a readable Context
  namespace, do not build its catalog from `MemoryStore.list_context_names()`
  alone. Use `ReadableContextCatalog` so effectively READ-granted public names
  and ordinary local names share the same command-local public hierarchy.
- Public names determine semantic parent/child placement. A Grant attachment
  is authorization metadata and must never be treated as a hierarchy edge.
  Keep the exact `ContextAccess` for every selected name so loading,
  revalidation, provider disclosure, and user-visible Grant annotation retain
  the correct owner and Grant identity.
- A readable name does not authorize every downstream use. Before provider
  inference, retained analysis, transfer, or mutation, apply that operation's
  `DERIVE`, `COMBINE`, `EXPORT`, `SAVE_*`, `ACCEPT_DERIVED`, and target-locality
  rules. Fail before provider connection when required authority is absent.
- QUERY-only routes may be shown only where the operation explicitly supports
  the authorized query interface. Never open or silently treat their hidden
  content as ordinary Memory input.

## Shared Context targeting

- Treat Context targets, lexical reach, namespace-tree navigation, and checked
  selection as one reusable component family under
  `memcommit.context_targeting`. Keep operation-neutral values in `model.py`,
  pure public-name expansion in `resolution.py`, merged Context loading in
  `loading.py`, search-only corpus construction in `search.py`, and
  prompt-toolkit state under `tui/`.
- Import the narrow owning module instead of reaching through another command
  or adding a parallel helper beside an operation. When a shared component
  grows into multiple related files, group them under one concept package and
  preserve a dependency direction from models and pure resolution toward
  integrations and presentation; core modules must not import operation code.
- Reuse `ContextTreeState`, `ContextSelectionState`, and `ContextReachState`
  for common cursor, checked-value, cardinality, and exact-versus-descendant
  mechanics. Keep availability, role validation, default values, receipts,
  authority, and materialization meaning in the calling operation.
- Allow a shared MULTIPLE `ContextSelectionState` to contain zero checked
  names while the person edits it. Enforce an operation's minimum only when
  constructing its executable request or typed receipt. SINGLE mode must
  contain exactly one name; when switching an empty MULTIPLE control to SINGLE,
  use the composing tree's visible cursor as the explicit fallback.
- For hierarchical MULTIPLE selection, compose the frozen Context tree with
  the shared selection state's group toggle: checking a parent checks its full
  lexical subtree and unchecking it clears that subtree. Render every effective
  target as checked and execute the exact checked set; do not also apply hidden
  descendant expansion that could re-include an independently unchecked row.
- Use `expand_lexical_context_names` for canonical name-prefix expansion.
  Keep lexical descendants and embedded-Context traversal as independent axes,
  and never interpret Grant attachment metadata as a hierarchy edge.
- Common in-memory controls do not imply a common persisted schema or a
  cross-launch preference. Preserve Compare, Update, Meld, and Sever's existing
  session formats and compatibility defaults through operation adapters;
  Find and new setup screens start from their explicit operation defaults.
- In the shared Save Location editor, keep direct exact-name input as the initial
  focus and render a frozen local Context parent tree above it when a catalog is
  available. Compose `ContextTreeState`, `ContextSelectionState`, and the common
  row renderer; Enter on a tree row reparents the current final name segment and
  returns to direct input. Browsing must not create, load, switch, rename, or
  persist a Context, and the operation's exact validator remains authoritative.
- Keep compatibility facades thin and free of implementation. New internal
  code must import `memcommit.context_targeting` modules directly rather than
  adding behavior to legacy `memcommit.context_scope` or command-local wrappers.

## Selective curation batches

- Forget and Sever share one batch semantic invariant: send the complete
  frozen Source frame and criterion frame in one provider turn, then require
  exactly one keep/transform/drop decision per Source Memory. Do not decompose
  the turn into independent per-Memory inference calls; neighboring Source
  Memories may supply necessary context.
- Treat a Forget instruction as one process-local `INSTRUCTION` criterion and
  Sever Criteria as a `MEMORY_FRAME`. Never render the instruction as a Memory
  or assign it fabricated durable provenance.
- Keep provider aliasing, complete-coverage validation, exact KEEP, nonempty
  TRANSFORM, and empty DROP invariants in the shared curation decoder. Preserve
  operation-specific variants in adapters.
- Sharing analysis and Resolution presentation does not share authority or
  materialization. Forget alone may update/delete its Source after its normal
  mutation checks; Sever must leave Source unchanged and create its reviewed
  require-new result under its derived-work permissions.
- Keep the implementation and rollout limitations consistent with
  `docs/selective-curation-design-rationale.md`.

## Terminal color semantics

### Shared terminal interaction mechanics

- Before adding operation-specific TUI state, rendering, focus traversal,
  scrolling, pointer, or key-navigation code, check the shared components in
  `memcommit.commands.tui_primitives`, `memcommit.selection`, Context/Memory
  pickers, and the common session workbench shells. Reuse or extend the narrowest
  applicable shared component instead of cloning its behavior into one command.
- Keep semantic meaning and validation in the calling command, but keep common
  interaction mechanics common. When a missing capability belongs to an
  existing shared pattern, add it to that shared component and migrate the
  relevant caller rather than introducing a parallel grammar.
- Project fixed flat choices through `SelectionOption` and
  `FlatSelectionState`. Use the common checked-card renderer for horizontal or
  stacked choices and the common tree marker/style projection for hierarchical
  selectors. Layout and operation key meanings may differ, but `✓`, retained
  selection color, focused border/color, escaping, and cursor-versus-selection
  meaning must not be redrawn by an operation.

- Keep report structure, explanatory prose, cards, and ordinary labels neutral
  white. Do not tint a whole Compare, Meld, Review, or Impact report merely to
  make it look grouped.
- Reserve the shared light lavender (`#cad3f5`) for text that represents an
  individual Memory object. Focus may temporarily replace that color with the
  shared blue focus treatment; selection, warning, and status colors retain
  their own explicit semantics.
- When adding a formatted report fragment, classify it by meaning before
  assigning a style. A box surrounding prose is report chrome, not a Memory,
  even when the report was derived from Memories.
- Across saved-session workbenches, bind both Escape and Backspace to the same
  one-level back-navigation path while focus is in a read-only surface. Do not
  steal Backspace from a composer or other writable input, where it must remain
  ordinary text deletion.
- Keep focused detail-card viewport behavior in the shared session Viewer, not
  in an operation-specific adapter. Place the hidden cursor anchor after the
  focused card's closing border so a lower card is not rendered as only a top
  edge at the bottom of the viewport.
- Treat OPTIONS in the shared Resolution Session `RESPONSES` frame as an explicit nested
  layer: Enter opens it, Up/Down moves, Enter selects, and Escape/Backspace
  returns to section navigation. Render every option with the common Meld-style
  checked card: `✓` marks the staged selection, retained selection keeps the
  common fill, and the keyboard target receives the heavy blue border. Do not
  use radio circles, diamonds, or operation-authored option boxes. When
  reopening a saved draft, initialize the option cursor on the checked choice so
  the visible selection and the next Enter target cannot disagree.
- In an actionable Ambiguity or Conflict detail, treat its clarification or
  resolution question and proposed readings or resolutions as one Decision
  focus section. One navigation step focuses both; Enter from that section
  opens the nested choice rows. Do not make the person focus the question and
  options separately when the question has no independent action.
- Open Different reading/resolution and ordinary item Response input inside
  the existing `RESPONSES` frame; never replace the current detail with a
  separate editor screen or add a sibling Message frame. Enter saves the
  response and returns focus to the same Responses frame, while `Ctrl-J` inserts a
  newline. A draft-owning adapter may persist that response without closing
  the workbench; operations that require a new semantic provider turn still
  receive their explicit submitted action.
- Make `RESPONSE` itself a focusable section after Decision inside the common
  Responses frame. Enter on that section opens its inline field. Do not render an
  adapter-authored instruction such as `REFINE, COMMENT, OR ENTER...` as if it
  were saved content; a new response starts blank, while reopening a durable
  draft restores its existing text.
- Keep the common Resolution Session topology as `VIEWER`, conditional
  `RESPONSES`, `ITEMS`, optional `SAVE LOCATION`, then `TO DO`. Responses is
  visible only for the currently opened answerable item or whole-set guidance.
  Items contains review targets only. To Do derives one next action:
  open an unresolved required conflict/item first, otherwise materialize the
  reviewed choices, apply an exact ready proposal, or expose the operation's
  whole-set resolution. Do not put Apply or Resolve All back into Items as a
  synthetic row, and do not let this presentation state bypass adapter action
  validation.
- Start a common Resolution Session with the complete report focused in
  Viewer. Visible-frame Tab order must follow the screen from the first
  interaction and after an item is opened:
  `VIEWER → ITEMS → TO DO → VIEWER` before an item is opened, and
  `VIEWER → RESPONSES → ITEMS → TO DO → VIEWER` for an answerable opened item;
  optional Save Location stays between Items and To Do. Shift-Tab follows the
  reverse order. Do not introduce a separate initial Items hub or skip the
  visible Responses or Items frame when leaving an opened Viewer.
- Keep a detail's ordinal (`n/total`) separate from review obligation. Show
  `REQUIRED n · OPTIONAL m` for the complete item set. To Do gates progression
  only on unanswered REQUIRED items; unanswered OPTIONAL items remain
  inspectable in Items but may be skipped when materializing or applying.
  Report their skipped or unanswered count explicitly.
- Result, Compare, and Resolution viewers share frame, focus, report-chrome,
  Memory-object, and option-card styles, but they do not share one semantic
  detail model. Result detail is a read-only evidence-to-outcome trace.
  Actionable Ambiguity and Conflict detail instead shows classification
  before source-linked evidence, followed by a type-specific reason, question,
  proposed readings or resolutions, and an independently stored response. For Meld,
  keep each relation adjacent to its exact Context/Memory members and group
  its member Memories into one claim per source frame; do not flatten issue
  evidence away from the relation that judged it or repeat the same Context
  heading for every supporting Memory.

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
  picker also renders `DIRECT SELECT · P` below provider-ranked suggestions.
  `P` opens the same name-only namespace tree as `mem switch`; its choice may
  join the process-local existing-name plan, but must not open Context records,
  bind anything, or enter the Ground-creation argv. This state must not load or
  validate an existing Context, switch to one, transmit
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
  `P` on Contexts, Rules, or Memories opens the same Context namespace tree.
  Before binding it uses only the frozen name catalog; after binding it is
  restricted to the frozen publication and placement target frames. The
  choice changes only the next reviewed BIND, Rule, or Ground Memory proposal.
  Newly proposed Rules retain their selected target UIDs; legacy Rules with
  empty target lists remain readable.
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
- In a collapsed read pane, `B` leaves the current Ground view and opens a
  freshly discovered saved-Ground picker; `Q` leaves `mem ground` entirely.
  Neither key applies a pending exact command, and returning with `B` must
  refresh identities, revisions, digests, and ordering before another Ground
  can open. Lowercase `b` and `q` remain ordinary text in Message, pane
  comments, direct edits, and exact-name fields, so a person starts from the
  general composer with `Tab` before using either navigation key. `C` remains
  the pane-comment compatibility alias and `Ctrl-C` remains immediate exit.
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

# Named common-grounding sessions

## Status

The implementation has two explicit stages. It first creates or resumes a
named empty version-1 scaffold, then an explicit binding action upgrades that
scaffold to a version-2 workbench:

```bash
mem ground \
  "I want to separate Task 1 into wiki and user-facing material."

mem ground task-1-fixture \
  --goal "Agree on the wiki and local Task 1 Memory contents." \
  --scope participant/campus-wiki-fork \
  --scope participant/construction-updates \
  --snapshot

mem ground task-1-fixture --snapshot

mem ground task-1-fixture \
  --description "Use verified Main Building changes to update the local wiki fork." \
  --raw-context temp/task-1 \
  --derived-context temp/task-1-atomized \
  --publication-target participant/campus-wiki-fork \
  --placement-target participant/construction-updates/building-access \
  --snapshot
```

The bound workbench can select a candidate, propose a Rule by itself,
attach multiple fit, boundary, or contrast Ground Memories to one rule, retain
the earlier combined rule/Memory shortcut, accept/refine/defer/reject a
proposal, and revise its Goal or one target criterion. Refining an accepted
rule or Ground Memory reopens it as `PROPOSED`; it must be accepted again. The
bound workbench does run a provider-backed, one-command-at-a-time semantic
dialogue for binding, Goal revision, Rule proposal, traceable Ground Memory
proposal, and Rule/Memory review.
It does not yet perform semantic regression automatically, approve the whole
Ground, or edit any Context. The blank-entry adapter creates only an initial
named Goal after approval, then continues into the named workbench. The empty
scaffold remains intentional: no rule or example is generated merely because
a session was created.

### Blank entry before naming

Running `mem ground` without a name has two environment-sensitive
presentations of the same unsaved state:

- with interactive stdin and stdout (a TTY), it opens a full-screen terminal
  UI (a TUI);
- outside a TTY, it prints a stable `WORKING · NOT SAVED` snapshot and exits
  without reading stdin or contacting a provider.

A natural-language positional value that cannot be a portable Ground name
starts the same unsaved flow with that exact value shown in the Goal pane:

```bash
mem ground "I want to separate Task 1 into wiki and user-facing material."
```

In a TTY, the request is immediately visible as the Working Goal and is
already `USER TURN 1`. It is not copied into the Message composer and does not
wait for a redundant `Enter`: the host performs content-free Context locator
discovery and starts one provider interpretation. The composer is empty when
the agent's proposal or question makes it the person's turn again. Outside a
TTY, the request is only rendered in the deterministic unsaved snapshot; no
provider is called and nothing is written. A valid portable positional value
such as `task-1` retains the established named-Ground create/resume behavior.
The explicit `--request` form disambiguates a short request that itself looks
like a portable name. This grammar preserves existing saved names while
making terminal turn-taking match ordinary conversation.

The starting sentence is a provisional orientation, not an automatically
approved or durable Goal. The raw wording remains visible through
clarification turns; a provider may propose a refined Goal and portable name,
but only the exact locally constructed creation command can save them. This is
**Goal-first in structure, entry-anywhere in
conversation**: a person may begin with an outcome, example, or uncertainty,
while the workbench obtains a revisable Working Goal before it binds evidence
or proposes Rules and Ground Memories.

### Goal, agreement, and the unsaved draft

Ground deliberately has no separate user-facing completion criterion. A
completion sentence duplicated the Goal while behaving like an unacknowledged
fourth normative layer: both fields tried to say what state the work should
make true. Grounding instead ends when the agent proposes that the current
Goal, Rules, and Memories express the common ground and the person explicitly
agrees with that exact state. Closing the TUI, reaching an item count, or
satisfying a model-generated predicate is not that agreement.

The current prototype does not yet persist a whole-Ground agreement event.
Saved Grounds therefore remain `OPEN`; `Escape` and `Q` close only the view.
A future durable agreement command must bind approval to the reviewed Ground
revision and digest. It must not infer agreement from coverage or reuse the
legacy completion field.

The blank TUI is already the appropriate temporary session: its Working Goal,
dialogue blocks, and pending proposal live only in process memory. Before the
exact creation command is approved, no Ground JSON, temporary name, Context
state, or checkpoint exists. Persisting an unnamed draft was rejected because
it would introduce resume identity, name collision, expiry, cleanup, and
privacy decisions without helping the immediate dialogue. A distinct
named-draft feature can be designed later if interrupted-session recovery
becomes necessary.

Lifecycle and persistence state belong to the overall artifact header. An
unsaved Ground says `MEM GROUND · WORKING · NOT SAVED`; a named one says
`WORKING · SAVED`. The initial Goal pane therefore contains only the Goal
text, while `PROPOSED` remains available to distinguish an unapproved
replacement candidate. Repeating `WORKING` or `NOT SAVED` inside one
component made it look like Goal had a different state from Contexts, Rules,
Memories, or Chat.

The first full-screen implementation kept Goal, Rules, and Memories in a short
fixed summary while Chat consumed most of the available height. An actual
use run showed that this hierarchy was misleading: the three editable Ground
layers looked like passive status labels, while the transcript looked like the
primary artifact. It also made a long Goal, Rule, or Ground Memory inaccessible
rather than merely compact.

The revised layout presents Goal, Contexts, Rules, Memories, and Chat as
five peer workbench components, but peers do not need identical height. Goal is an
orientation statement: every newly created or revised durable Goal is limited
to 40 whitespace-delimited words, and its frame is capped at three visible
body rows. Contexts prefers five body rows, and may use up to eight, because its
first-turn picker must show Current, Main, alternatives, a possible new-Context
suggestion, and the evidence boundary together. Rules, Memories, and Chat
share the remaining flexible height. Every component keeps its own focusable,
independently scrollable viewport:

```text
┌─ GOAL ────────────────────────────────────────────────┐
│ (not yet stated)                                  ▐   │
└───────────────────────────────────────────────────────┘
┌─ CONTEXTS ────────────────────────────────────────────┐
│ CURRENT · test/update/from · NOT BOUND            ▐   │
│ MAIN? · temp/task-1 · NOT BOUND                        │
└───────────────────────────────────────────────────────┘
┌─ RULES ───────────────────────────────────────────────┐
│ (none yet)                                        ▐   │
└───────────────────────────────────────────────────────┘
┌─ MEMORIES ────────────────────────────────────────────┐
│ (none yet)                                        ▐   │
└───────────────────────────────────────────────────────┘
┌─ CHAT ────────────────────────────────────────────────┐
│ What are you trying to understand, decide, or make?▐  │
│─ MESSAGE ─────────────────────────────────────────────│
│ ›                                                     │
└───────────────────────────────────────────────────────┘
```

The Message field belongs inside Chat's outer frame, not in a second adjacent
frame. When the person enters Goal, Contexts, Rules, or Memories, that same
buffer moves into the selected outer frame as `COMMENT (FOR THE AGENT)` and
returns to Chat on collapse. The exchange therefore reads as a conversation
inside the Ground component whose uncertainty is being discussed.

The cap prevents an almost-always-short Goal from reserving empty rows while
the evidence panes and the Chat pane need space. The raw starting request is
exempt because it is provisional dialogue, not yet a saved Goal; if it is
long, the three-row viewport scrolls until the provider distills a proposed
Goal. Existing version 1/2 Grounds with longer Goals also remain loadable and
scrollable. New initial proposals, CLI creation, and Goal revisions reject a
41st word before approval or persistence. Counting by whitespace is
deliberately deterministic but imperfect for languages normally written
without spaces; a later tokenizer-aware rule must preserve the same
cross-provider predictability.

Every read pane uses a three-row frame minimum so the five panes and one
in-frame composer still fit a conventional 24-row terminal with at least one
visible body row in every component. The active host temporarily grows enough
to retain a reading row, internal label, and input row. At 30 rows Contexts
reaches its five-body-row preference;
prompt-toolkit's normal Dimension solver compresses it on smaller terminals
rather than relying on a hard-coded terminal-size branch. Goal remains capped
at three body rows and Contexts at eight, while Rules, Memories, and Chat
have equal weight and no maximum. Those three panels therefore divide all
surplus height instead of leaving an unused band below Action on a tall
terminal. Their contents remain bounded by independent scrollable viewports,
not by a fixed panel maximum. The shared primitive's default remains unchanged
for other commands. `Tab` and
`Shift-Tab` move focus among the five viewports and embedded composer. Focus
no longer changes a panel's semantic title.
Instead, the frame border and label become bold light blue. This keeps panel
identity stable while providing both weight and color cues; prompt-toolkit's
built-in Frame has no safe per-instance heavy-border glyph set, so true
double-width border characters remain a non-goal.

Arrow and page-navigation keys normally scroll the focused read-only viewport.
During provisional Context selection, `Up` and `Down` instead move among the
frozen candidates only while `CONTEXTS` is focused, `Space` toggles the
current name, `F` finishes or reopens the local plan, and `N` opens an exact
new-name editor. `Enter` opens a Context-focused conversation just as it does
for the other semantic panes. `PageUp`/`PageDown` retain
viewport scrolling. During exact approval, arrow keys switch the command and
effects view only while Chat itself is focused; after Tab moves focus to
Memories or another read pane, the same arrows remain local to that pane.
Ground supplies a visual-row page binding because
prompt-toolkit's default moves by logical lines and therefore cannot page
through one long wrapped Korean or English paragraph. Its scrollbar likewise
measures wrapped visual height and the in-line vertical offset, so the thumb
moves with the viewport instead of remaining at the top and merely changing
size. When the composer has focus, its normal editing keys remain local to
the editor. An internal labelled rule separates the composer from its host
pane's read viewport, while the shared outer border keeps it from reading as a
sixth workbench component. The typing boundary remains recognizable to users
familiar with conversation-first terminal agents without detaching the turn
from its immediate referent.

Both blank and named Ground applications explicitly enable prompt-toolkit's
page-navigation bindings as a fallback and install the wrapped-row correction
only while a read-only pane has focus. Integration tests use narrow terminals
and a single long logical line to verify a changed visual viewport, then move
away with `Tab` and return with `Shift-Tab`. Ground deliberately does not
install a global arrow- or page-key override: the Message composer must retain
cursor editing, and `CONTEXTS` must retain candidate movement during
provisional selection.

The in-frame Message composer retains enough room for a short multiline
correction.
The command-review Action panel is content-sized instead of sharing one
stretchable height across every mode: approval uses two body rows, while
interpretation and apply errors use one. Its exact command and effects remain
in the scrollable Chat pane. The compact Action frame therefore keeps the
navigation, approval, refinement, and exit boundary visible without gaining
blank rows on tall terminals or clipping a third instruction row at 24 rows.

`CONTEXTS` is a visible workbench frame, not a fourth semantic result layer
beside Goal–Rules–Memories. A blank TUI may show the current Context name as an
at-launch orientation snapshot, but an unbound Ground still states that no
Context was bound. The current pointer is neither evidence nor a default
selection. A bound Ground renders only recorded role, name, and binding-time
direct-item counts for raw evidence, working candidates, publication target,
and placement targets. It does not load live Context content, expose UIDs or
digests, or claim current freshness; the normal mutation boundary rechecks
freshness later.

Within an input field, `Enter` sends and `Ctrl-J` inserts a newline. On a
read-only Goal, Contexts, Rules, or Memories viewport, `Enter` first opens that
pane's conversation; on Chat it focuses the already-present general Message.
`Escape` first collapses an expanded pane conversation and restores any
unsent general Chat draft, then cancels or closes the TUI on a subsequent
press. No discarded draft is interpreted or persisted. Ground deliberately
does not also bind `Alt-Enter`: terminal applications commonly encode it as
an Escape-prefixed Enter sequence, which would make a lone Escape wait or
fail to provide the predictable exit requested by the user.

When an exact command is awaiting approval, the command/effect receipt and its
operation-specific approval keys take precedence over message entry. The
five workbench components remain visible, but the approval focus is attached
to Chat. `Tab` and `Shift-Tab` may still browse the five read-only panes
after a pane has been scrolled, but every writable in-frame composer is
detached and the Action panel is shown below the workbench. Browsing cannot
edit, replace, or implicitly approve the
frozen command; approval remains bound to the exact displayed argv.

This is the normal entry point when the person has only a rough concern, such
as wanting to work out which parts of some notes were reported. Early
grounding should not require a session identifier, polished Goal, Rules, or
Memories. The person can answer in ordinary language; the Codex-backed adapter
then returns either one consequential `ASK` turn or a structured
`PROPOSE(name, goal)` turn. The provider never supplies a command.
The host validates and freezes those two fields, constructs the exact
creation argv locally, and presents it for explicit approval.

The blank frame is not an unnamed persistent Ground. It does not construct a
store, reserve a name, inspect the current Context, or write dialogue text.
Its optional Working Goal is an unsaved copy of the person's starting request,
not an inferred durable field. Persisting an unnamed session would weaken
identity and resume semantics, while silently generating a slug could collide
with an existing Ground or make an unreviewed interpretation durable. Named
action options therefore still require `GROUND_NAME`; `mem ground --goal ...`,
`--snapshot`, or another action option without a name fails without creating
state. A provider-suggested name is checked for a collision before approval
and checked again immediately before execution.

### Content-free Context discovery before naming

A sentence-form invocation is already a submitted request, so the next
conversational turn belongs to the agent. The blank TUI now performs one
bounded discovery-and-interpretation turn before waiting for another message:

```text
submit the desired outcome
→ show one local CURRENT pointer immediately
→ discover ordinary Context storage locators without opening their files
→ cycle THINKING. → THINKING.. → THINKING… while the provider compares names
→ give aliases and bounded local path names to the first provider interpretation
→ show exactly one MAIN? and up to three ALTERNATIVE names
→ optionally show one separate NEW? name below the existing alternatives
→ always show ADD NEW CONTEXT below it for an exact person-supplied name
→ show process-local Rule and Memory drafts when the turn supports them
→ auto-focus CONTEXTS and highlight MAIN?
→ let Tab/Shift-Tab traverse panes and Up/Down move across Context rows
→ let Space toggle existing names; N edits NEW? or ADD NEW CONTEXT
→ let F finish or reopen a Context plan; Enter opens pane conversation
→ hide every unselected alternative but retain a separate NOT CREATED plan
→ only then expose the unchanged Ground name/Goal creation approval
```

The empty Rules and Memories panes say that drafts may appear "as the Ground
takes shape," rather than promising that they appear after the first agent
turn or after a proper Context is found. Draft readiness depends on the
available grounding, while this first pass reads only Context locator names
and therefore cannot claim that it found or verified the proper Context.

`MemoryStore.list_context_names()` could not satisfy this contract because it
`json.load()`s every complete `context.json` in order to validate its header.
Since Memory text is inline in that same object, even a name-only return value
would materialize content. Ground therefore uses a separate locator scanner.
It derives ordinary Context names from regular, non-symlink
`contexts/**/context.json` paths and calls only path validation; it never opens
the record. A corrupt or path/header-mismatched record can consequently appear
as `LOCATOR_ONLY`. That is honest rather than unsafe: discovery is not
validation, and the normal load plus version/digest boundary must still reject
an invalid Context before binding.

Current orientation, discovery, recommendation, and binding remain different
states:

- **current** means `state.json` named one Context when the TUI opened; it is a
  mutable local pointer, not evidence or authority;
- **discovered** means an unverified ordinary storage locator exists;
- **recommended** means its public name makes it the best available starting
  workspace or a runner-up;
- **selected** means the person chose one or more displayed locator names in
  this in-memory TUI only; the first is local Main and the rest are additional
  hints, while all remain unvalidated, unsaved, and unbound;
- **suggested-new** means the provider proposed a canonical ordinary Context
  name that does not exist; it is not a discovered locator and has no
  checkbox. `N` may copy it into a process-local exact-name editor, but the
  edited value is still neither selected, initialized, persisted, nor bound;
- **direct-new** means the person entered an exact new Context name through the
  separate blank editor. It has the same process-local `NOT CREATED` boundary
  as suggested-new and is not an existing-Context selection;
- **bound** means the person approved an exact versioned frame command after
  normal Context validation.

The first semantic call receives the submitted dialogue and at most 64
locators as ephemeral aliases such as `c0001`. For a larger store, a
deterministic local name-token ranking bounds the candidate set. The provider
must return exactly one `MAIN` alias when the catalog is non-empty and may
return at most three distinct `ALTERNATIVE` aliases, each with a short reason.
The host maps only aliases it introduced back to their names and rejects zero
or several Main candidates. This ranks “which workspace should we inspect
first?” without preventing the person from retaining several relevant names.
It does not prematurely decide whether a Context is raw evidence, a derived
artifact, or a publication target.

Each Context record is one logical output line. Reasons do not consume a
second row, and visual wrapping remains the terminal's responsibility:

```text
NAME-ONLY CHECK · NOT BOUND
CURRENT · test/update/from · NO DISPLAYED MATCH · NOT BOUND
› [ ] MAIN? · temp/task-1 · NOT BOUND — strongest Task 1 name match
  [ ] ALTERNATIVE · temp/task-1-atomized · NOT BOUND — processed variant
  [ ] ALTERNATIVE · temp/task-1-atomized-en · NOT BOUND — English variant
  NEW? · ticker-rule-examples · NOT CREATED
  ADD NEW CONTEXT · N to enter an exact Context name
```

After checking two names and pressing `F`, unselected alternatives
disappear:

```text
SELECTED CONTEXTS · 2 · NOT BOUND
MAIN · temp/task-1 · SELECTED · NOT BOUND — strongest Task 1 name match
ADDITIONAL · temp/task-1-atomized · SELECTED · NOT BOUND — processed variant
EVIDENCE · locator names only; binding still needs approval
```

The TUI snapshots the current name once from `state.json` and displays it
locally before provider work starts. The provider receives the same ordinary
alias/name catalog regardless; it is not told which alias, if any, was
current. The host compares the returned Main and alternatives with the local
snapshot to annotate the Current row. This avoids turning a global pointer,
which can change in another terminal, into hidden semantic evidence.

The locator scan and provider payload omit the active/current marker, durable
UIDs, Memory text, item counts, `context_ref` and `memory_ref` contents,
query-only aliases and routing data, query-source files, and existing Ground
contents. Query-only public aliases are embedded inside a parent
`context.json`; safely cataloguing them later requires a content-free sidecar
or metadata index rather than opening that record during blank Ground startup.

The provider call runs in a daemon worker after the full-screen application
has started. This is necessary for `CURRENT` and an animated
`THINKING.` / `THINKING..` / `THINKING…` cue to be visible rather than
printing a completed result after an unexplained pause. The animation is only
a liveness cue: it does not claim semantic progress or expose provider state.
It updates only the Context viewport, preserving the independent scroll
positions of Goal, Rules, Memories, and Chat, and stops when interpretation
finishes, fails, or the shell closes. The daemon worker also prevents
application-loop shutdown from joining a blocking provider call. While a call
is running, another submission is not accepted. `Escape` and `Ctrl-C` close
the TUI immediately. A synchronous provider process may finish after that
close, but a closed-shell guard discards its result; it cannot produce an
approval, run a command, or change Ground state. Actively terminating the
provider subprocess remains a separate cancellation boundary.

Context names themselves can still be sensitive metadata. Passing the
sentence-form request explicitly starts this bounded provider turn; bare
`mem ground` continues to wait for a first user message, and non-TTY rendering
remains provider-free. A future UI may add an opt-out or local-only discovery
mode if the research deployment needs a stricter name-disclosure boundary.

The Context picker is deliberately a local name-only narrowing step. A
provider `PROPOSE` with candidates first enters `CONTEXT_SELECTION`; it does
not expose Ground-creation approval until the person toggles at least one
existing candidate with `Space`, or records one process-local new name, and
finishes the picker. The first checked existing name is shown as local Main and
later names as additional hints. `Up` and `Down` also reach `NEW?` and
`ADD NEW CONTEXT`, but `Space` never checks either row. `N` on `NEW?` opens
the in-frame exact-name editor with the proposed value; `N` on
`ADD NEW CONTEXT` opens it blank initially and reopens the current local name
prefilled after one has been entered. The same ordinary new-Context syntax and
read-only creatability checks apply to both, including slash-delimited names.
Submitting an unchanged `NEW?` value explicitly accepts that suggestion;
accepting either editor records only a process-local `NOT CREATED` plan. Finishing
collapses the pane to selected existing names plus that separate new-name plan
and hides unselected alternatives.

Neither form of `N` is a `mem` command or mutation approval. Moving,
checking, opening, and directly editing picker rows perform no provider call,
Context load, creation, `mem switch`, `state.json` update, Ground write, or
checkpoint. A separately submitted `COMMENT (FOR THE AGENT)` remains an agent
turn, but its provider payload contains only that comment: the catalog
suggestion and exact process-local new name are deliberately omitted. While
approval is pending, focusing the collapsed Context pane and pressing `F`
reopens the same frozen set and its local new-name plan. `N` on an ADD row may
suspend the receipt before editing, but no writable field coexists with exact
approval. `Enter` remains the ordinary Context-focused conversation action
whenever input mode permits one.

The subsequent `A` still approves exactly
`mem ground NAME --goal GOAL`; its effect receipt says Context selections are
local only and Contexts remain unchanged. An ignored provider `NEW?` is labeled
`unaccepted`, while only an editor-accepted name is called a local Context
plan. Starting another semantic
interpretation clears and reranks the provisional choice.

Selected existing names and a suggested, edited, or directly entered new name
are not sent to either provider, added to `GroundShellProposal`, persisted in
Ground JSON, inserted into Ground creation argv, or recovered after restart.
After creation they may continue only in process memory into the unbound named
Ground screen, where the pane distinguishes selected `NOT BOUND` names from a
new `NOT CREATED` plan and says that explicit frame roles still need a separate
approved bind. Saved frames replace the existing-name hints after binding;
creating a planned new Context still requires a separate exact `mem init`.
Closing the process discards all of these hints. They supply no freshness,
validity, ownership, or operational-role claim. The first-turn provider
question may therefore ask only about the Goal and portable Ground name, not
treat any selected or planned Context name as part of creation approval.

A later binding picker still needs to inspect validated Contexts and ask the
person to assign operational roles rather than merely choose this starting
name:

- raw evidence;
- derived or atomized candidates;
- writable publication/materialization target; and
- one or more placement targets.

For Task 1, this would let the person select the raw notes and atomized
candidates, distinguish the participant's writable campus-wiki fork from the
opaque organizational wiki, and select the six construction-update placement
Contexts. The organizational wiki may be shown as a query-only authority, but
it cannot be opened by the picker or silently substituted for a writable local
target.

After that later role assignment the host constructs one exact `mem ground`
binding argv locally, states which frames will be fingerprinted and saved, and
waits for the existing dedicated approval action. Candidate ranking may use
the weak signals above, but no Context is bound from terminal location, the
active Context, name similarity, recency, the provisional Goal, or the local
Main marker. This keeps a helpful “start from nothing” path compatible with
the privacy, multi-Context, and one-command approval boundaries. Context
loading, role editing, and the binding picker remain future work.

Existing Rules and Ground Memories are also intentionally not copied into this
first turn. Ground-session filenames can eventually be discovered without
opening their records and shown as `RELATED GROUND · NOT INSPECTED`; inspecting
one would be a separate user-visible action. Reusing its accepted Rules or
Ground Memories also needs provenance that records which Ground revision
supplied them.
Without that contract, automatic reuse would turn an opaque old artifact into
hidden authority.

The current provider is the existing one-shot Codex adapter authenticated by
the local ChatGPT login. Each blank interpretation is ephemeral and receives
the submitted user turns plus the bounded alias/name locator catalog. It does
not receive the current Context marker, any Memory, query-only content,
existing Grounds, durable identities, or command authority. `ASK` turns
accumulate the bounded user replies explicitly rather than relying on hidden
provider conversation state. Claude, MCP, or an internal provider can later
implement the same structured boundary.

On a proposal, the TUI shows the locally rendered command and lists every
effect: one Ground is created, its Goal is set, and Rules, Ground Memories,
Contexts, Context Memories, and checkpoints are unchanged. Only the
dedicated `A` action approves that exact frozen proposal. `E` returns it for
refinement, while `Q`, Escape, Ctrl-C, provider failure, malformed output, or
name collision leave state unchanged. The approved argv is dispatched through
the ordinary `memcommit.cli` entry point as an argument vector, never through
a shell, and its actual output is reported after the TUI closes.

The original blank-entry slice ended after creating or cancelling one initial
Ground. The continuing vertical slice now enters the named-Ground TUI
immediately after creation and also opens that TUI when an existing name is
entered without options in a terminal. The five-component view
changes from `WORKING · NOT SAVED` to `WORKING · SAVED · UNBOUND`, then to
`WORKING · SAVED · BOUND` after an explicitly approved binding command.

The continuing loop supports one exact command at a time for binding, Goal
revision, Rule proposal, Rule/Ground-Memory review, and traceable Ground Memory
proposal.
Proposal and acceptance remain separate approvals. After every success the
Ground is reloaded and the Goal, Contexts, Rules, Memories, and Chat
components are refreshed. The displayed command carries the reviewed Ground
UID, revision, and serialized
digest as a save-boundary version token. A binding command additionally
freezes each selected Context's UID, digest, and direct-item counts because an
unbound Ground has no saved frames yet. The normal CLI locks and rechecks the
bound Context frames, then atomically compares the saved Ground under its own
lock before replacing it. A concurrent Ground or evidence-frame change
invalidates the pending command without applying it. Before a later semantic
turn, and after any unconfirmed application, the TUI reloads the saved Ground
instead of continuing from a stale panel or retrying an old approval.
Ordinary non-replacement Ground mutations use the state they first loaded as
an implicit compare-and-swap precondition too, so an older non-interactive
writer cannot overwrite a newer TUI-approved mutation.

### Pane-local edit and agent comment

Ground uses the same human grounding move in two different forms: a person may
know the exact replacement already, or may want the agent to reason about an
uncertainty before either side proposes a change. Pressing `Enter` on Goal,
Contexts, Rules, or Memories therefore expands a conversation inside that
pane; Chat has the same Message surface open by default. Pressing `E` on a
directly editable Goal, saved Rule, or saved Memory expands the selected pane
with two deliberately non-synonymous fields:

```text
EDIT (DIRECTLY)
> the exact replacement text

COMMENT (FOR THE AGENT)
> an explanation, question, correction, or additional context
```

Chat is the whole-Ground conversational orchestrator, not another durable
semantic layer. A comment stays visibly attached to the pane from which it
was opened so the agent retains its immediate referent, but that focus does
not fence the turn's semantic consequences: it may expose a needed change in
Goal, Contexts, Rules, or Memories. Any such cross-layer effect still becomes
at most one separately reviewed command. By contrast, `EDIT (DIRECTLY)` is an
exact replacement constraint for the selected target only and never
authorizes collateral rewrites. If direct text and a comment are submitted
together, the comment is rationale for that one local proposal. A broader
implication is raised in a later comment-only turn so it cannot hitchhike on
the direct edit's approval.

Every focused read pane also accepts `C` as a compatibility alias for its
conversation. `Enter` deliberately has one cross-pane meaning; potentially
consequential item actions moved to explicit mnemonic keys. `E` means direct
edit, `R` reviews the selected READY Rule draft, and the blank Context picker
uses `Space` to toggle, `F` to finish or reopen, and `N` for an exact new name.
In the blank Ground, Rules and Memories are provider-authored previews, so
their focused comments carry only the panel label and raw comment; preview
text is not folded back into `USER_EXACT` evidence. In a named Ground, a saved
`rN` or `cN` alias may identify the selected item because the provider already
receives that Ground-local alias through the normal saved-Ground payload.

Neither field is labelled `optional`. A blank field is permitted, but the
labels describe who has authority over its contents rather than suggesting a
form-completion hierarchy. `Tab` and `Shift-Tab` move only between the two
fields, `Ctrl-J` inserts a newline, and `Enter` reviews their combined turn.
The first `Escape` discards and collapses this local editor; only a subsequent
`Escape` closes Ground. While an exact command is awaiting approval the editor
cannot open, so browsing a pane can never modify the frozen argv.

The expanded layout reuses the existing Message composer as
`COMMENT (FOR THE AGENT)` and moves it inside the selected pane's existing
outer frame. A direct-edit expansion additionally inserts `EDIT (DIRECTLY)`;
a comment-only expansion does not. The composer exists in exactly one live
layout branch at a time, and Escape restores its suspended general draft when
the pane conversation is cancelled. This keeps all five reading panes rendered at 24
rows; duplicating the composer or nesting a second Frame would either exceed
the terminal budget or visually split one conversation into two components.

Direct text is an exact constraint, not a prompt for stylistic rewriting. In
the blank, unnamed screen, the host validates the directly edited Goal, asks
the provider for a portable name, and rejects the entire response if the
returned Goal differs from the edit. In a named Ground, the host locally
reduces the exact edit to one version-guarded proposal and still waits for
`A`. Returning such a proposal for refinement reopens the same direct-edit
and agent-comment fields; it must not paste their host-framed payload into the
ordinary Message composer, because doing so would downgrade exact user
wording into provider-authored dialogue. This restoration applies before an
apply attempt. If application returns an uncertain error, refinement instead
discards the direct draft and requires the pane to be reopened, because
reconstructing its receipt could duplicate a mutation that actually crossed
the external save boundary. The saved schema-version-1 scaffold remains
bind-only so it can still be
upgraded without rewriting identity: revise its Goal before creation, or bind
it before directly revising saved items. A comment-only submission is a
focused semantic turn: the provider sees `GOAL`, `RULE rN`, or `MEMORY cN` as
visible local focus, while the raw comment remains the draft-source text.

The direct boundary follows the actual data model:

- Goal replaces the complete Goal and retains the 40-word authoring limit;
- Rules first select one stable `rN` item, then `REFINE` only that Rule;
- Memories first select one stable `cN` item, then edit only its `EXPECTED`
  output. Its source content remains immutable trace evidence;
- Contexts keep their structured name/role selection and binding flow because
  free text cannot safely represent frame roles, identities, or freshness;
- Chat owns the general in-frame Message composer and is not recursively
  editable.

Rules and Memories use `Up`/`Down` to choose one saved item before `E`.
`R` reviews a selected READY Rule draft or reclassifies a stale draft queue;
`Enter` remains the pane-conversation action in either state. These selection
boundaries are necessary for the one-response,
one-command invariant: editing an aggregate pane rendering could otherwise
imply several mutations. A comment attached to a Rule or Memory refinement is
visible process-local agent context but is not a new durable rationale field;
persisting such comments separately remains a schema extension rather than
being hidden inside the edited text.

### Ground Memories and storage compatibility

`MEMORIES` is the user-facing third Ground layer. One entry is a reviewed
judgment over a source Context Memory: it retains that source text and digest,
its linked Rule, fit/boundary/contrast role, include/exclude/unresolved
disposition, target Contexts, rationale, and expected result. It is not a
second ordinary Memory inserted into a Context merely by appearing here.

Semantically, each Ground Memory is a **Case** even though the enclosing layer
keeps the Memory vocabulary. The interactive list presents every Case as one
compact three-line card:

```text
c1 [PROPOSED · FIT / INCLUDE]
North Star Energy Inc. → NSE
NOTES · Ignore the legal suffix and use the remaining initials.
```

This is a presentation contract, not a stored-schema migration: `content`,
`expected`, and `rationale` remain the serialized field names. The arrow's
left and right sides display input and output; the third row always makes the
Ground-local note slot visible, using `(none)` when it is empty. Embedded
newlines are folded to `↵` in this list only, without rewriting stored text.
The selected Case may expand read-only `DETAILS` for linked Rules, source
references, and targets; unselected Cases remain three-line cards. A later
`fill` or other materialization operation may propose the arrow's right side
as ordinary Context content, but it must not copy `NOTES`. One independently
reviewable example is one Ground Memory, so a nine-cell evaluation matrix
normally contains nine Cases rather than one aggregate Memory. Multiline input
or output remains one Case when its lines jointly describe one example.

For example, a ticker generator may start with `North Star Energy Inc.` →
`NSE`. A later `North Star Energy Inc., Class B` → `NSE.B` boundary Case can
refine an initial uppercase-initials Rule to preserve the `.B` class suffix.
This example is generative rather than a lookup of an official ticker: the
Cases teach and test the transformation Rule.

Existing Ground JSON and exact commands predate this vocabulary. They retain
`kind: "CASE"`, `case_role`, `PROPOSE_CASE`, `--case-role`,
`--minimum-cases`, the provider payload key `cases`, stable `cN` aliases,
`INDUCED_FROM_CASES`, and persisted review Decision text such as
`ACCEPT CASE`. Changing those tokens in place would alter serialized digests,
pending compare-and-swap receipts, and legacy loading. The UI, help, effects,
and provider prose therefore say Ground Memory or Memories—displaying the
last two examples as `INDUCED_FROM_MEMORIES` and `ACCEPT MEMORY`—while the
parser and wire schema keep the compatibility tokens. A later schema
migration would need dual parsing and explicit versioning rather than a
display-only rename.

### List and table views for Ground Memories

Ground Memories support two equivalent read-only presentations inside the
same focusable pane. `LIST` remains the default and preserves the compact
one-line blank-draft previews and three-line saved-Memory cards used by the
existing review and editing flow. `TABLE` exposes the same records as cells so
several examples can be compared by field without parsing repeated tags or
card headings. Pressing `V` while MEMORIES is focused switches in either
direction; it is deliberately scoped to that pane so typing `v` in Message is
still ordinary text.

The blank table separates `FROM` and `CHECK`, turning labels such as
`[Suggested] [Unverified]` into independently comparable cells alongside
input, expected output, role, decision, and Rule. The named table exposes
status, role, decision, input, expected output, Notes, linked Rules, and source
and target counts. `Up`/`Down` clamp at the first and last Memory;
`Left`/`Right` clamp at the first and last column. The selected cell is
reverse-bold, its full folded value appears beneath the grid, and the buffer
cursor follows it so a non-wrapping table scrolls horizontally on narrower
terminals. `Tab` still leaves the whole Memories pane, `Enter` opens a
conversation anchored to the selected row, `E` directly edits that saved
row's expected output, and the default List continues to wrap normally.

This is presentation state, not Ground state. View mode and cell coordinates
are process-local, reset to List when a shell starts, and are clamped when a
provider batch or reloaded Ground changes row count. They are never sent to a
provider, persisted in Ground JSON, included in a digest or exact command, or
treated as approval. During exact approval the same grid navigation remains
available because command/effects arrows are active only when Chat is
focused; `A` still applies the unchanged frozen receipt.

### First-turn Rule and Memory previews

The opening sentence may already contain a usable Goal, one or more examples,
or enough structure for a tentative Rule. Waiting until after creation to show
all of that made the Rules and Memories panes look artificially empty and hid
what the agent had understood. The first provider turn may therefore return a
bounded, process-local preview batch alongside the proposed Goal:

```text
RULES
r1 [Suggested] [Unverified] Use a short uppercase base code and preserve share-class suffixes.

MEMORIES
c1 [Suggested] [Unverified] Apple Inc. | AAPL · FIT / UNRESOLVED · r1
c2 [Suggested] [Unverified] Berkshire Hathaway, Class B | BRK.B · BOUNDARY / UNRESOLVED · r1
c3 [Suggested] [Unverified] North Star Energy Inc. | NSE · CONTRAST / UNRESOLVED · r1
```

These are not `GroundItem` records. Ground creation still executes only
`mem ground NAME --goal GOAL`, and its receipt continues to say Rules and
Memories are unchanged. A durable Ground Memory requires an exact source
Memory in a bound working-candidate Context and at least one bound target, so a
first-turn preview cannot bypass Context creation, binding, proposal, or review.

Provenance is explicit even at the preview layer without spending two heading
lines per item. `USER_EXACT` requires one or more verbatim spans from the
submitted CLI dialogue and renders `[Provided] [Source-matched]`; source
matching confirms who supplied the text, not that the mapping is true. Every
displayed USER_EXACT Rule content and Memory content/nonempty expected field
must itself occur verbatim inside those verified spans. Merely finding an
unrelated user phrase somewhere in the turn cannot authorize the label.
`AGENT_SUGGESTED` requires no source span and renders
`[Suggested] [Unverified]`; it is a proposed test, not an official ticker or
other authoritative fact, and its disposition remains `UNRESOLVED`. The
quoted Korean request about finding a reusable company-name/ticker Rule
contains no Apple or Berkshire mapping by itself, so examples generated from
that request must use the latter label. If `Apple Inc. -> AAPL` appears in the
actual `mem ground` request, it may use the former label after exact-span
verification.

The provider should offer one to three useful Memory previews when examples
clarify the tentative Rule. If the person supplied none, clearly marked
synthetic examples are especially useful: even a mistaken example gives the
person a concrete correction direction. Variety matters more than count, so a
straightforward fit plus a boundary or contrast is more useful than three
near-duplicates. The provider must not manufacture redundant examples merely
to fill three slots, and an empty batch remains preferable when no grounded or
useful synthetic test is available. The typed preview retains its rationale,
but the overview deliberately omits it so every first-turn Rule and Memory
occupies one logical line. A later detail surface can expose that rationale
without returning the main workbench to the repeated multi-line card design.

A new Context possibility follows the same non-authoritative boundary:

```text
MAIN? · existing-examples · NOT BOUND
ALTERNATIVE · naming-notes · NOT BOUND
NEW? · test/ground/ticker-rule-examples · NOT CREATED
ADD NEW CONTEXT · N to enter an exact Context name
```

`NEW?` and `ADD NEW CONTEXT` are deliberately outside the existing-locator
checkbox list. `N` opens the same in-frame editor, prefilled for `NEW?` and
blank for the first direct entry; later direct edits reopen the local plan
prefilled. The person can therefore repair a weak suggestion or enter a
namespaced Context the name-only catalog could not recommend. The accepted
text remains process-local and `NOT CREATED`; it never enters selected Context
hints, the Ground JSON, the Ground creation argv, or binding state. If the
person chooses that direction, a future turn must separately review and
approve `mem init test/ground/ticker-rule-examples`, then separately bind the
created Context. Ground creation, Context initialization, and frame binding
are not collapsed into one approval.

The exact Context-name field is deliberately one line because a newline can
never pass ordinary Context-name validation. Its footer therefore sends
`Ctrl-J` users to the adjacent multiline `COMMENT (FOR THE AGENT)` field
rather than advertising an impossible name input.

`ADD NEW CONTEXT` remains visible after discovery even when the catalog is
empty and the provider returns no `NEW?`. Immediate `A` approval remains valid
in that case; moving to Contexts and pressing `N` explicitly suspends the
approval layer before the editor opens, then restores the unchanged Ground
receipt for a fresh `A` only after the local name passes validation. When
there is no existing candidate, the picker also renders
`CONTINUE WITHOUT CONTEXT PLAN · Review Ground only`. This keeps a provider
`NEW?` optional rather than turning an unaccepted suggestion into a creation
gate.

### Long requirement turns and Rule granularity

A person's single message may contain many constraints, background facts, and
examples. It must not be copied wholesale into one Rule. A Rule is one
independently reviewable, reusable judgment criterion; a concrete campus
layout, observed behavior, or expected answer belongs in a Ground Memory or
in the fixture Context itself. Unknown scope stays in Chat as an open
question instead of being normalized into a guessed Rule.

The named-turn schema now has a read-only `DRAFTS` result in addition to
single `ASK` and action results. When the final user turn contains multiple
independently reviewable units, one provider call must return the complete
ordered batch rather than selecting an arbitrary first Rule. Each draft is
displayed as `RULE`, `FACT`, `MEMORY`, `GOAL`, or `QUESTION`, and as `READY`,
`NEEDS_CLARIFICATION`, `DUPLICATE`, or `CONFLICT`. The provider wire retains
`CASE` for the displayed `MEMORY` kind so the strict compatibility schema does
not change. The provider supplies
normalized content and a classification reason. It must also quote one or
more exact spans from the submitted turn; the host rejects a span that is not
a verbatim substring. In a visible multi-turn transcript, earlier turns may
clarify the final user turn, but agent-authored text is not draft source
material.

The batch appears below saved Rules as `DRAFTS · NOT SAVED`. `Up` and `Down`
select drafts while the Rules pane has focus. A non-Rule or non-`READY` draft
cannot produce a command and instead remains a clarification cue. Pressing
`R` on one `READY` Rule reduces only that selected draft, locally, to the
normal version-guarded `--propose-rule` receipt. `A` is still required to run
that one command. The saved item is only `PROPOSED`; a later
`REVIEW_ITEM/ACCEPT` action and a second approval are required before it
becomes accepted authority. Remaining drafts survive that applied command
inside the open TUI, but every status changes visibly to `STALE`; none can
reach command review. Pressing `R` runs one new read-only classification of
the original submitted comment against the updated saved Ground. Only a
freshly returned `READY` Rule may then be prepared against that revision.
This extra pass is necessary because the first saved Rule may make a remaining
candidate duplicate or conflicting even though its argv could carry a fresh
version guard. A new user correction or follow-up similarly marks the old
queue stale before inference begins, so an `ASK` response or provider failure
cannot leave a superseded `READY` candidate actionable. Only a successful
replacement `DRAFTS` response can clear that state. A Ground revision changed
by another writer instead discards the local draft queue and requires the
person to submit the comment again, because the broader dialogue and saved
state may both have changed.

This queue is deliberately process-local. Closing the TUI discards every
unselected draft, and none is represented as a saved Rule, Ground Memory,
Context, Context Memory, or checkpoint. An unbound Ground may display a read-only
classification preview, but selecting a Rule cannot reach command review
until explicit Context frames have been bound through their separately
approved command. The current Rule schema also forbids source references, so
exact comment spans are available while the draft is unsaved but are not
durable after proposal. A later dialogue-source schema must solve resumability
and durable trace without hiding quotes inside rationale text.

These choices retain three boundaries: one state-changing command per user
response, one Rule per proposal approval, and separate proposal versus
acceptance approvals. They also make the long pasted list useful immediately:
the provider performs atomization and classification once, while the person
reviews the resulting units rather than repeatedly asking the model to
reinterpret the whole comment.

The named provider payload contains the portable Ground name, Goal,
Rule/Ground-Memory text and rationale, their local `rN`/`cN` aliases and relations,
state and revision, bound Context names, and the current visible dialogue
cycle. The final raw user turn is carried as a separate draft-source field, so
the host validates exact spans against that turn rather than against earlier
user or agent text. This is enough to classify the submitted comment against
saved Ground items. It does not contain live Context projections, source
references, or durable UIDs. A saved Ground Memory's text may be an earlier
exact copy of source Context Memory content, but its source identity remains
local. A source selector typed for a new Ground Memory is matched locally and
replaced with a stable
`mN` alias before inference; only an alias actually introduced by that
redaction can be mapped back into the reviewed command. Because such an alias
cannot be an exact durable quote from the person's comment, `DRAFTS` fails
closed when selector redaction changed the current draft source. The person
must remove the selector or handle that referenced Ground Memory separately.

Natural-language transcript persistence and asynchronous provider progress
remain follow-up work. Non-TTY output remains deterministic so remote
captures, tests, and surrounding agents do not hang on a terminal prompt.
The multiline Message buffer and its standalone frame remain state-free
terminal chrome and are also used by meld. Ground additionally mounts that
buffer inside the active semantic pane. Ground still owns its ASK/PROPOSE
controller, exact-command receipt, reload/CAS guards, and one-command approval
lifecycle; sharing the editor does not make those semantics generic.
The reusable presentation boundary and its rejected alternatives are recorded
in
[`shared-tui-command-review-design-rationale.md`](shared-tui-command-review-design-rationale.md).

### Implemented target focus and agent-mediated command loop

The first interactive vertical slice deliberately keeps semantic
interpretation outside the Ground persistence engine. A target-focused,
read-only view is available as:

```bash
mem ground task-1-fixture --focus-target participant/campus-wiki-fork
```

The screen focuses one bound target, restates the saved Goal and target
requirement, shows the exact raw/candidate/target frames, exposes a recorded
blocker, and ends with one consequential question. It omits the complete
target ledger, candidate list, method readings, UUIDs, and digests that remain
available in `--snapshot`. The view changes no Ground data. It may also be
combined with one Goal or target-requirement revision so that the same command
shows the post-action focused state. Other actions retain their existing
output until focused Rule and Ground Memory receipts are designed; `--focus-target`
currently rejects those combinations rather than hiding the affected item
behind aggregate counts.

In this prototype the person may answer in the blank-entry TUI, continue in
the named-Ground TUI, or work through a surrounding agent conversation. The
relevant adapter maps that answer to at most one existing state-changing
`mem` command, displays the exact command and its Goal, Rules, or Ground Memories effect,
and waits for explicit approval. One approval authorizes only that command.
The adapter may then run it through the ordinary CLI path and must obtain
separate approval before a follow-up command. Commands proven to be read-only
do not consume this approval. In particular, focus rendering of an existing
Ground is read-only; the legacy `mem ground NAME --snapshot` form is
creation-capable when `NAME` does not exist and must not be treated as
inspection until existence has been confirmed.

This split is intentional:

- `ground` stores and validates the jointly revised Goal, Rules, and Memories;
- the agent interprets natural-language turns and selects one deterministic
  CLI action;
- existing commands remain the mutation boundary; and
- Context changes continue to use `add`, `edit`, `update`, or another
  purpose-specific operation rather than direct JSON edits by `ground`.

The current slice adds a semantic interpretation adapter, not a second
persistence engine. It does not persist natural-language dialogue turns or
batch multiple mutations into one approval. Starting with one real command per
turn lets the design acquire missing Goal/Rule/Memory primitives from observed
interactions rather than speculating about a complete transition engine. If a
later turn regularly requires several inseparable actions, an atomic round
command can be designed from that evidence.

The atomize workbench remains a concrete precedent for consequential
follow-ups, corrections, and explicit permission. Atomize-specific issue
identities, source arity, and edit proposals stay in its adapter. No current
atomize grounding session is a named Ground, and no named Ground automatically
contributes evidence to atomization.

Artifact migration,
cross-operation import/export, and a shared schema are deferred until their
compatibility and provenance boundaries are designed. The focused rationale
is recorded in
[`mem-review-conversational-grounding-design-rationale.md`](mem-review-conversational-grounding-design-rationale.md).

### Generalization target: Goal–Rules–Memories alignment

`mem ground` should generalize the conversational pattern proven by atomize:
the person and agent use consequential follow-up questions to align three
revisable layers rather than treating the first request as a fixed form.

| Layer | Grounding role |
| --- | --- |
| `GOAL` | The desired outcome: what the session is trying to make true. |
| `RULES` | Inspectable, revisable rules for interpreting evidence, making judgments, proposing actions, and deciding what the current operation may apply. |
| `MEMORIES` | Concrete judgments about exact artifacts. Proposed Ground Memories test the current Goal and Rules; explicitly approved Ground Memories become regression anchors. |

These three layers are the Ground's result, jointly revised by the person and
agent. `ground` does not produce a separate result artifact. A later
purpose-specific operation may use the accepted Ground to propose changes to a
Context, but that Context is not a fourth Ground layer.

`Goal`, `Rules`, and `Memories` are stable user-facing type names. Whether they have become
shared or remain provisional belongs in item and session status, not in names
such as `Shared Goal` or `Working Rules`. The serialized field
`contract_name` remains an internal version-1/version-2 compatibility name;
new user-facing output calls the artifact a named Ground.

The source Context Memory and the reviewed Ground Memory are related but not
identical. In atomize, Context Memories are the concrete artifacts being
judged. A Ground Memory records the expected reading, judgment, or outcome for
an exact source Memory or group of Memories. Merely being inspected, affected,
or edited does not make a source Memory a golden Ground Memory; that accepted
status requires explicit approval.

A difficult Ground Memory can reveal that a Rule or even the Goal is wrong.
Grounding is therefore bidirectional rather than a one-way process of fitting
examples to an immutable specification. Its reusable dialogue should be:

```text
show a concrete mismatch or candidate
→ ask a follow-up whose answer could change a Goal, Rule, Ground Memory judgment,
  or downstream action
→ restate the agent's provisional understanding and its consequences
→ let the user confirm, extend, correct, retract, defer, or add exact context
→ revise the affected layer and recheck dependent Ground Memories
→ request explicit approval before canonicalization or mutation
```

Follow-ups must be consequential. A generic request for more detail is not
enough; the interface should say which judgment or proposed action cannot be
settled without the answer. The user may choose a suggested reading, enter a
different reading, revise a Rule, add a closer Ground Memory, or revise the Goal
when lower-level evidence exposes a bad Goal boundary.

The first two representative applications are fixed as follows.

1. **Atomize ambiguity resolution.** The Goal is to reduce actionable
   ambiguity until the selected reading and consequential Memory changes match
   the reviewer's intent, not to eliminate every imaginable linguistic
   reading. Rules describe how the agent may judge readings, propagate
   supplied context, identify affected Memories, and propose or apply edits.
   The source and affected Memories are the concrete artifacts; reviewed
   readings and expected outcomes are the candidate Ground Memories. A clarification
   may resolve one Memory, expose a downstream Memory that must change, or
   reveal that the agent's scope extension is wrong.
2. **Task fixture and wiki co-design.** The Goal is to agree on what the
   campus wiki and local construction-update fixture must represent and where
   each Memory belongs. Rules describe evidence requirements,
   categories, placement, coverage, non-invention, and audience or disclosure
   judgments within the fixed privacy boundary. Ground Memories bind source
   examples to expected fixture content, placement, or disposition. A
   follow-up may add a missing Ground Memory, refine a Rule, or reveal that the
   original Goal was incomplete; accepted Ground Memories become regression
   anchors for later candidates.

These two examples are the initial design targets, not an exhaustive operation
list. The current provider-backed adapter uses existing deterministic Ground
commands for revision and approval. Any later asynchronous or cross-operation
dialogue controller must preserve the same one-command permission and
application boundaries.

Rules are adjustable task knowledge, not a way to negotiate away
implementation invariants. Privacy restrictions, query-only opacity,
provenance requirements, stale-frame validation, and explicit mutation
authority remain hard system boundaries. Interpreting atomize through
Goal–Rules–Memories also does not convert an atomize session into a named
Ground, promote an affected Context Memory into a golden Ground Memory, or synchronize the two
schemas. Any transfer requires a separate explicit provenance and
compatibility contract.

## Decision

`ground` is the session-level operation for a person and an agent to establish
and maintain a local Goal–Rules–Memories Ground. The Ground itself is the
jointly produced result. It grows through concrete Ground Memories, readable
Rules, corrections, boundary examples, and explicit decisions.

The long-term loop is:

```text
present one concrete source Memory
→ judge it against the currently accepted Ground
→ retrieve a supporting Ground Memory and a materially close contrast
→ apply the Rules, curate a Ground Memory, or induct a Rule delta
→ show the Rule and Ground Memory diff
→ let the user accept, correct, supply context, or enter a closer Memory
→ regression-check previously accepted Ground Memories
→ repeat
```

Retrieval of supporting and contrast Ground Memories, semantic regression, and
whole-Ground approval are not yet automated.

The operation is complete only locally: reviewed Ground Memories in the named
scope are adequately explained, unresolved boundaries remain explicit,
regression checks pass, and the user explicitly approves the Ground. Neither
the model nor a count threshold may infer approval.

## Operation hierarchy

The discussion originally gave `induct` too much responsibility. The revised
hierarchy is:

| Concept | Responsibility |
| --- | --- |
| `ground` | Persist and validate Goal–Rules–Memories judgments through deterministic actions used by the conversational orchestrator. |
| coverage check | Judge whether the current Rules and accepted Ground Memories already explain a candidate. This is a stage, not a new public `fit` command. |
| `induct` | Propose a reusable Rule, exception, narrowing, or broadening from reviewed Ground Memories. |
| Memory curation | Find, enter, or retain fit, boundary, and contrast Ground Memories. It is initially an internal grounding action rather than a public command. |
| regression check | Show whether a proposed Rule or Ground Memory decision changes previously accepted judgments. |
| `fill` | Use an established requirement/evidence Ground to propose missing target content. |
| `dream` | Perform background discovery or consolidation; it may enqueue a grounding candidate but cannot approve it. |
| `review` | Provide a reusable interaction surface for an already defined finding adapter; it is not the semantic grounding process. |

The earlier `fit` notes use `YES / MAY / NO` for whether Memories fit together
inside a Context. Reusing the public name for Memory-to-Rule coverage would make
those polarities ambiguous. Grounding documentation may use the ordinary
phrase "fit the current rule," but the first CLI should call that stage a
coverage check.

## Why the name is `ground`

The name comes from the project's own research history rather than only from
an external analogy.

- IdeenKasten `20260324193916` explicitly calls iterating rules with an AI a
  "common grounding" step.
- `20260324193907`–`20260324193910` describes the human providing approximate
  intent, the AI proposing a readable logical rule, the human reviewing it,
  and the system showing a rule diff.
- `20260324193917` turns the `all-too-common` cloze failure into a concrete
  boundary case that corrects an overly broad exception.
- `20260427090004`–`20260427090010` repeats the same sequence: expected
  input/output examples, a proposed rule, a failure revealing an incorrect
  boundary, a correction, and a rerun. `20260427090007` explicitly requires
  repetition.
- `20250922034205` observes that collecting Memories without a user-editable
  grounding and review process is insufficient.
- `20251112083908` describes common ground as a network the user and AI build
  together to prevent interpretation errors from accumulating.

The relevant local, non-vendored archive is:

```text
IdeenKasten/gum_projects/using_ideenkasten/my_GUM_data.json
```

`calibrate` was considered as the public name. It describes adjusting a fixed
boundary, but it does not comfortably include forming new rules, establishing
vocabulary, or constructing shared task knowledge. `teach` and `train` make
the interaction sound one-directional or like parameter training. `align` is
too broad and collides with AI-alignment terminology. `ground` preserves the
mutual, longitudinal meaning already present in the local record.

## Common grounding versus evidence grounding

Memcommit also uses "grounding" to mean that an atomized claim is supported by
a source span. These meanings must remain explicit:

- **evidence grounding** asks whether a stored claim is supported by its
  declared source;
- **common grounding** asks whether the user and agent have established a
  shared, inspectable local Ground for interpreting and judging Ground
  Memories.

One does not prove the other. A source-supported sentence can still be
interpreted differently, and a mutually accepted rule can still lack adequate
source evidence.

## Agent-suggested external precedents

The following readings were introduced by the agent during the naming and
workflow discussion. They are saved for later reading as external design
precedents, not as user-provided requirements, adopted dependencies, or proof
that memcommit should copy their representations.

1. Gonzalo Ramos et al.,
   [Interactive machine teaching: a human-centered approach to building
   machine-learned models](https://www.microsoft.com/en-us/research/publication/interactive-machine-teaching-a-human-centered-approach-to-building-machine-learned-models/).
   The relevant resemblance is an iterative human-guided process that produces
   inspectable task behavior. Memcommit grounding is broader and need not train
   model weights.
2. Debbie Richards,
   [Two decades of Ripple Down Rules
   research](https://doi.org/10.1017/S0269888909000241).
   The relevant resemblance is case-triggered rule refinement that preserves
   previously accepted case judgments through contrastive cases. Memcommit
   does not adopt the RDR tree format.

Each new session records these references with:

```text
provenance = AGENT_SUGGESTED_EXTERNAL_PRECEDENT
reading_status = UNREAD
```

This preserves who introduced the material and prevents an unread reference
from silently becoming part of the accepted Ground.
`UNREAD` specifically means that the user has not marked the saved reference
as read in memcommit; it does not claim that no agent, author, or other person
has read the source.

## Named-session identity

Grounding is not bound to the global current Context. A Task 1 Ground may
cover `participant/campus-wiki-fork` plus several local construction-update Contexts, while a
different agent works on Task 2. Therefore sessions are named and independent:

```text
~/.mem/ground-sessions/
├── task-1-fixture.json
├── task-2-fixture.json
└── task-3-fixture.json
```

The portable Ground name is restricted to:

```text
[a-z0-9][a-z0-9._-]{0,127}
```

It is an identity label, not a path. `/`, `..`, uppercase letters, spaces,
control characters, Windows device names such as `con` and `nul`, and
symbolic-link storage are rejected. Running the same name again resumes the
same UID without rewriting its bytes. Creation options cannot silently
redefine an existing Ground; `--replace-ground` is the explicit
destructive/recovery boundary.

There is deliberately no active-Ground pointer. Requiring a name for every
persisted Ground avoids a global switch whose state could collide across
terminals or agents. The named form remains intentionally create-or-resume, so
`--snapshot` also creates an empty Ground when the supplied name does not
exist and a mistyped direct name can still create an extra empty file.

Interactive bare `mem ground` now mitigates that discovery problem with a
read-only saved-work launcher and an explicit New action. The selected row is
reloaded through an existing-only path after the picker closes; it never falls
through to create-or-resume if the file disappeared. The launcher sorts by
physical last-saved time or name and groups by bound Context, without creating
an active Ground pointer. Ground rename and archive remain future CLI work.

The initial Ground view is `BY CONTEXT · RECENT FIRST`: Context groups use
case-insensitive name order with an exact-name tie breaker, and sessions within
one group use physical last-saved time. A Ground appears only once, under its
first `RAW_EVIDENCE` frame, then its first `WORKING_CANDIDATES` frame, or
`Unbound` when neither exists. Every bound Context remains visible in detail
and searchable. A scrolled slice repeats its first heading as `CONTINUED`, and
its height budget counts headings and separators so the selected session cannot
be hidden by grouping chrome.

Ground JSON remains store-level rather than Context-owned. The launcher shows
the frozen process profile and store root above the list so this physical
boundary is visible. It derives the profile label by matching that frozen root
against all registered profile roots instead of trusting the registry's live
active pointer, which another terminal can change after the process imports
and freezes its store.

## Schema

Version 1 saves:

- a canonical session UUID;
- portable Ground name;
- Goal;
- a required `completion_criterion` compatibility key inherited from the
  prototype's earlier model;
- descriptive scope labels;
- `OPEN` status and revision zero;
- an empty item list reserved for future `RULE`, `CASE`, `ISSUE`, and
  `DECISION` records;
- attributed methodological references.

The schema describes the intended shape of future items—origin (`USER`,
`AGENT`, or `JOINT`), status, iteration, rationale, expected result, and
related-item references—but version 1 rejects every non-empty item list. It
also rejects `GROUNDED`, nonzero revisions, substituted references, and even a
boolean masquerading as schema version `1`. This fail-closed boundary prevents
hand-edited JSON from impersonating user approval before decision and
regression invariants exist.

The version 1 and version 2 `completion_criterion` key remains serialized,
validated, and included in record digests solely so existing Ground JSON and
compare-and-swap checks continue to round-trip exactly. New commands cannot
set it, renderers do not display it, and neither initial nor named semantic
providers receive it. Removing the key requires an explicit schema migration;
silently changing the v1/v2 record shape would break old files and their
digests.

Version 2 is introduced only by explicit frame binding. It additionally saves:

- a copied, content-digested source brief;
- exact raw, derived, publication-target, and placement-target Context frames;
- an editable Goal and editable per-target requirements;
- proposed or reviewed Rules, Ground Memories, and decisions;
- structured source-Memory and target-Context references;
- a rule provenance of `USER_STATED`, `DISTILLED_FROM_GOAL`,
  `INDUCED_FROM_CASES`, or `JOINTLY_REVISED`; and
- one durable candidate cursor.

Version 1 remains fail-closed and is never silently reinterpreted as version
2. A saved Rule/Memory proposal and a review decision each advance the
   semantic revision exactly once. Moving the cursor does not.

The whole serialized object is strictly revalidated before atomic replacement.
Load rejects duplicate JSON keys, unknown fields, malformed UUIDs, unknown
references, invalid names, and symbolic links.

## Task 1 runtime authority revision

The runtime update design now separates the organizational wiki authority from
the participant's writable materialization target:

```text
campus-wiki                         query-only organizational origin
participant/campus-wiki-fork        provisioned writable local scope
participant/construction-updates    verified change evidence
```

`impact` and `update` target the local fork. The organizational origin may be
queried through an opaque pointer and is only a future publication target.
Query access does not grant traversal or mutation authority.

The Ground fixture follows that authority split: it binds the writable
`participant/campus-wiki-fork` and the
`participant/construction-updates/*` hierarchy as ordinary Context frames.
It never binds `campus-wiki`, loads its query-only contents, or presents it as
a Ground Memory destination.

One adapter name remains intentionally behind the runtime model. Ground's
version-2 schema and CLI still call the fork frame `PUBLICATION_TARGET` and
`--publication-target`. For Task 1 those labels mean “the local
materialization target from which a later contribution may be prepared”; they
do not mean that the shared origin is bound or that publication occurs.
Renaming that generic role in the persisted schema would require an explicit
schema migration. A future Ground version should represent the writable
materialization target and query-only upstream publication authority as
separate fields.

The local fork is assumed to be a current, researcher-provisioned snapshot of
the participant's complete authorized candidate scope, with no concurrent
upstream change during Task 1. It must not contain only pages already known to
change, because doing so would answer the impact-scope question during setup.
These are scenario assumptions until origin revisions, refresh, remote
divergence checks, and publication are implemented.

The small Ground regression fixture still initializes that bound fork with
zero Memories so it can exercise an explicit `BLOCKED` criterion. That
synthetic absence tests Ground behavior; it is not the participant-facing
Task 1 dataset and must not be read as permission to invent an upstream
baseline.

## Confirmed Task 1 frame

The Task 1 grounding surface has two deliberately different regions. This is a
data-model distinction, not merely a proposed screen layout.

The **upper region is the editable Ground**, expressed in three layers:

1. `GOAL`: the top-level result the fixture and operation should achieve;
2. `RULES — DISTILLED / INDUCED`: generalizations distilled
   top-down from the Goal, induced bottom-up from Ground Memories, stated by
   the user, or jointly revised; and
3. `MEMORIES — FIT / BOUNDARY / CONTRAST`: proposed or reviewed examples that
   fit or challenge the current Rules. Only explicitly accepted Ground
   Memories are golden regression anchors.

The copied Task description is displayed above these layers as a fixed source
brief. It is evidence about why the workbench exists, not the entire editable
Ground. Target-specific success criteria are displayed inside the Goal layer,
not as a fourth semantic layer. The Goal and those criteria may change when
lower Ground Memories expose a poor category, impossible requirement, or missing
distinction. Such a change is a new revision with its reason recorded; it is
not a silent edit.

The upper region says what must exist when the fixture is adequate, what is
currently missing, which decisions have been approved, and which gaps remain.
It contains:

- the fixed Task 1 source brief and editable Goal;
- the expected `participant/campus-wiki-fork` baseline and local
  materialization role;
- the six required local destination slots;
- each slot's ledger-derived `EMPTY`, `PARTIAL`, or `COVERED` state, or its
  explicitly recorded `BLOCKED` state;
- Rules and accepted golden Ground Memories that justify coverage; and
- unresolved requirements that must not be filled by invention.

The required local slots are:

```text
participant/construction-updates/building-access
participant/construction-updates/event-relocations
participant/construction-updates/temporary-parking
participant/construction-updates/shop-updates
participant/construction-updates/facility-updates
participant/construction-updates/route-changes
```

The synthetic Ground regression fixture initializes
`participant/campus-wiki-fork` and all six local Contexts with zero direct
Memories. The participant-facing scenario instead assumes a provisioned local
fork of the extensive organizational source. The regression session records
an explicit `BLOCKED` reason for its deliberately absent local-fork baseline;
it must not silently treat the construction notes as the pre-existing wiki or
synthesize a baseline. `ground` displays this recorded judgment but does not
infer it from the empty Context alone.

The four target states are a derived display, not a fourth Ground layer:

| State | Meaning |
| --- | --- |
| `EMPTY` | No accepted `INCLUDE` Ground Memory backed by an accepted Rule satisfies the slot. |
| `PARTIAL` | Some such distinct source Memories satisfy the slot, but the recorded minimum is not met. |
| `COVERED` | The recorded minimum is met by accepted `INCLUDE` Ground Memories backed by accepted Rules, counting each source Memory once per target. |
| `BLOCKED` | The session records a judgment that continuing requires missing evidence. This is not inferred automatically. |

These are grounding-ledger states, not a count of files in a directory.
`EMPTY`, `PARTIAL`, and `COVERED` are derived from the reviewed ledger;
`BLOCKED` is currently an explicit criterion field. For example, the current
notes describe event closures and parking closures but do not give a concrete
relocated event destination or replacement parking location. The session may
record those targets as blocked until evidence or the criterion changes.

The **lower region is the evidence-to-target workbench**. Its bound frames are:

```text
raw evidence       temp/task-1                    51 Memories
working candidates temp/task-1-atomized           54 Memories
targets            local fork + six construction-update child Contexts
```

The 51-to-54 change identifies the inspected input and derived candidate set;
it is not by itself evidence that atomization succeeded. The current schema
content-addresses each Ground Memory to exactly one source Memory in the working-candidate
Context. It does **not** yet persist the candidate-to-raw span mapping, so the
snapshot does not claim to show a raw trace. The workbench can select a
candidate, propose targets and expected wording, attach it to an existing
Rule, and accept, refine, defer, or reject it. `REFINE` currently
changes Rule wording or a Ground Memory's expected output; changing a Ground
Memory's targets,
role, disposition, rationale, or raw provenance remains follow-up work. A
proposed placement may name `participant/campus-wiki-fork`, one of the six
local slots, or both when their distinct source-of-change and materialization
roles justify the duplication. It may not name the query-only `campus-wiki`
origin.

The upper Ground must not be mixed into the lower candidate list. The top
answers “what are we trying to achieve, what rules currently express it, and
which reviewed Ground Memories support those Rules?” The bottom answers “what evidence
and derived candidates can justify or revise a particular target decision?”

This is deliberately bidirectional. A Goal or Rule may suggest how to judge a
lower Ground Memory, while a stubborn or awkward lower Ground Memory may
justify revising the Rule or even the Goal. An accepted Rule can be refined
and reopened. Because only accepted Rules support coverage, its accepted
Ground Memories stop contributing to `COVERED` until the revised Rule is
accepted again. A Goal or target-criterion revision is recorded with a reason,
but automatic semantic regression of prior Ground Memories remains follow-up
work.

## Proposed and golden Ground Memories

An agent-produced Ground Memory is `PROPOSED`. It has no accepted authority,
does not count toward `COVERED`, and is not a regression anchor. A **golden
Ground Memory** is the user-approved form of a concrete judgment: its evidence
trace, target slot, expected target content or disposition, and rationale have
all been reviewed. Golden Ground Memories may be tagged as fit, boundary, or
contrast evidence, but the tag does not replace explicit approval.

The implemented deterministic slice supports the following recorded actions:

```text
select one of the 54 bound working candidates
→ show its wording and candidate UID/digest
→ propose a Rule alone, or attach a Ground Memory to an existing Rule
→ propose target Contexts, expected wording, disposition, and rationale
→ let the user accept, refine expected wording, defer, or reject
→ save that decision only in the named ground session
→ recalculate target status from accepted INCLUDE Ground Memories and Rules
```

If the user refines the proposed expected output, the revised proposal must be
accepted before it may become a golden Ground Memory. A deferred Ground Memory becomes
`DEFERRED` and does not improve target coverage. Missing-context entry,
target/disposition correction, and automatic regression reporting are not yet
part of the Ground-Memory review action; a target criterion can instead be revised
explicitly with a recorded reason.

This vertical slice establishes one bound candidate, one content-addressed
candidate reference, one target decision, one explicit approval boundary, and
one derived status change. It deliberately does not claim a raw trace or
semantic regression result. Subsequent fixture work should establish at least
one approved seed Ground Memory for each coverable target slot rather than assuming
that an empty slot is explained by its name.

## Bound frames and stale work

A semantic ground session must bind every frame it reads rather than repeatedly
consulting mutable current Context state. The implemented binding records the
Context UID, locator, canonical digest, and direct-Memory count for the raw,
candidate, and target frames. The Task 1 description should be copied into or
content-addressed by the Ground so that moving an attachment does not change
the brief being reviewed.

Named turns reload the saved Ground before inference. An `ASK` turn does not
load live Context projections because none enter its provider payload. After
an actionable turn, the adapter verifies the recorded frames before freezing
the receipt, and the CLI verifies them again under Context locks before the
Ground save. A change to any bound raw, candidate, or target Context marks the
workbench `STALE`. Prior proposals and reasoning remain inspectable as history,
but stale work cannot:

- be promoted to a golden Ground Memory;
- change a slot to `COVERED`;
- support a future whole-Ground agreement record; or
- be exported for later target application.

There is no refresh/fork command in this slice. Today the reviewer must create
a new named Ground, or deliberately use `--replace-ground` and repeat the
explicit binding. A future non-destructive refresh should create a new
revision and require affected proposals to be checked against the new frame;
it must not silently rebase an old judgment onto changed evidence.

The current binding hashes the Context projection returned by the store
loader. A broken or unresolved `context_ref` can be omitted before that
projection is digested, so version 2 does not prove that every serialized
pointer was resolvable at binding time. The Task 1 frames use directly owned
Memories, but a future reference-aware Ground must hash the raw stored item
ledger as well as the resolved projection and report unresolved references
explicitly.

## First snapshot

An empty snapshot intentionally exposes absence rather than inventing a
starting rule:

```text
GROUND · task-1-fixture · OPEN
Revision: 0

GOAL
  Agree on the wiki and local Task 1 Memory contents.

SCOPE  participant/campus-wiki-fork, participant/construction-updates
RULES 0 · MEMORIES 0 · UNRESOLVED 0 · DECISIONS 0

No grounding material has been recorded.
The session is ready for jointly reviewed Rules and Ground Memories.
```

The snapshot also shows the two agent-suggested readings and their `UNREAD`
status. Terminal control characters are neutralized.

## Mutation, privacy, and approval boundaries

Creating or resuming an unbound ground does not read a Context. Binding and
rendering a bound workbench do load its recorded direct Context projections
to calculate and verify digests. Across both paths, `ground`:

- does not require a current Context;
- keeps provider access in the explicit TTY dialogue adapters; deterministic
  option-bearing CLI mutations and snapshots do not initiate inference;
- never opens a query-only source; a bound snapshot may display the selected
  direct working-candidate Memory;
- does not alter `state.json`, a Context, or a checkpoint;
- never treats provider output as approval; only a separately approved exact
  review command can mark a Rule or Ground Memory accepted.

This non-mutation boundary remains in force for the implemented workbench.
Reviewing a placement, promoting a proposal to a golden Ground Memory,
changing an upper-region status, or even marking the Ground `GROUNDED`
changes only the named Ground artifact. It must not add, edit, or delete a
Memory in
`participant/campus-wiki-fork`, `participant/construction-updates`, or either
temporary source Context, and must not create a target checkpoint.
Materializing approved decisions into target Contexts is a separate, explicit
future action with its own preview and checkpoint boundary. The query-only
`campus-wiki` origin is outside these bound frames altogether.

During semantic turns, query-only content remains opaque. Direct Context
evidence is fingerprinted before a command proposal and checked again under
locks before that round is saved. A changed frame may leave prior reasoning
inspectable, but it blocks the pending mutation. The current recovery is a
fresh interpretation against the reloaded Ground, or explicit
replacement/rebinding when the bound frames themselves are stale;
refresh/fork remains future work.

`GROUNDED` will require explicit user approval, no unresolved required
boundaries, at least one accepted Rule or Ground Memory, and a regression
report for the approved revision. A provider cannot set this status by itself.

## Task 1 use

The first named Ground is `task-1-fixture`. Its Goal is to establish which
Memories belong in the local `participant/campus-wiki-fork` fixture and which
belong in the six `participant/construction-updates/*` Contexts. The local
fork and verified change hierarchy have different materialization and
source-placement roles, so an explicitly justified fact may appear in both;
identical content is not automatically an accidental duplicate. The
query-only `campus-wiki` origin remains outside this Ground and becomes
relevant only at a later contribution boundary.

Within a future retrieval- and regression-enhanced review loop, the workbench
should submit one
concrete placement or content Ground Memory, show its raw trace plus the
nearest supporting and contrast Ground Memories, then let the user:

- apply the current Rules;
- correct the proposed judgment;
- refine or add a rule;
- retain the Ground Memory as fit, boundary, or contrast evidence;
- enter a closer Ground Memory or missing context; or
- defer the candidate.

The current deterministic slice records Rules, Ground Memories,
candidate-level references, and explicit decisions. Raw trace retrieval,
nearest-Ground-Memory retrieval, automatic batching of live Context
candidates, and whole-Ground approval remain future work. The process-local
`DRAFTS` batch covers only the person's current submitted comment.

## Alternatives and intentional limitations

- Reusing `ReviewSession` was rejected because its schema and rendering are
  specifically tied to ambiguity findings, reading choices, one Context
  digest, and one response field.
- A single active `ground-session.json` was rejected because Task 1, Task 2,
  and multiple agents would overwrite or switch shared global state.
- Automatically seeding rules from the external readings was rejected because
  methodological resemblance is not accepted domain knowledge.
- Automatically binding the empty ground to current Context bytes was rejected.
  Binding is now explicit because the Task 1 Ground spans multiple Contexts
  and the source/target choices are part of the experiment.
- Treating the 51 raw Memories and 54 candidates as the target Ground was
  rejected because evidence availability and fixture requirements answer
  different questions.
- Inferring a plausible `participant/campus-wiki-fork` baseline was rejected because it would
  conceal the target fixture's current absence and make before/after update
  behavior impossible to audit.
- Writing approved ground decisions directly into target Contexts was rejected
  because review, Ground approval, and data materialization need separate
  failure and consent boundaries.
- Treating every provider proposal as a golden example was rejected because it
  would let generated judgments bootstrap their own apparent coverage.
- Chat-to-TUI remote control, a semantic regression evaluator, target
  materialization action, whole-Ground approval action, and archive/fork
  workflow are not implemented in this slice. The implemented TUI does use
  arrow keys to switch between command and effects, and exact interactive
  mutations use a save-boundary compare-and-swap guard.
- Importance ordering, durable creation-time ordering, affected-decision estimates,
  automatic batch generation from live Context evidence, inherited or
  predecessor Context handling, and integrated ambiguity/conflict resolution
  remain deferred. One-shot batching of the person's current Ground comment is
  implemented; it does not imply retrieval or batch materialization.
  The first user-study slice may preserve the original Memory order.
- Frame digests currently cover the store-loaded projection, not a separate
  raw serialized pointer ledger; unresolved `context_ref` detection is
  deferred to a reference-aware binding version.

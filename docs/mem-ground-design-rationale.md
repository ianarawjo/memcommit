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
attach multiple fit, boundary, or contrast cases to one rule, retain the
earlier combined rule/case shortcut, accept/refine/defer/reject a proposal, and
revise its Goal or one target criterion. Refining an accepted rule or case
reopens it as `PROPOSED`; it must be accepted again. The bound workbench does
run a provider-backed, one-command-at-a-time semantic dialogue for binding,
Goal revision, Rule proposal, traceable Case proposal, and Rule/Case review.
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
- outside a TTY, it prints a stable `NEW` snapshot and exits without reading
  stdin or contacting a provider.

A natural-language positional value that cannot be a portable Ground name
starts the same unsaved flow with that exact value shown as a `WORKING` Goal:

```bash
mem ground "I want to separate Task 1 into wiki and user-facing material."
```

In a TTY, the request is immediately visible as the Working Goal and is
prefilled into the Message composer. The person may press `Enter` to submit
that exact first dialogue turn, edit it first, or press `Escape` before any
provider call. Outside a TTY, it is only rendered in the deterministic
unsaved snapshot; no provider is called and nothing is written. A valid
portable positional value such as `task-1` retains the established
named-Ground create/resume behavior. The explicit `--request` form
disambiguates a short request that itself looks like a portable name. This
grammar preserves existing saved names while removing the need to retype the
starting Goal inside the TUI.

The starting sentence is a provisional orientation, not an automatically
approved or durable Goal. The raw wording remains visible through
clarification turns; a provider may propose a refined Goal, completion
criterion, and portable name, but only the exact locally constructed creation
command can save them. This is **Goal-first in structure, entry-anywhere in
conversation**: a person may begin with an outcome, example, or uncertainty,
while the workbench obtains a revisable Working Goal before it binds evidence
or proposes Rules and Cases.

The first full-screen implementation kept Goal, Rules, and Cases in a short
fixed summary while Dialogue consumed most of the available height. An actual
use run showed that this hierarchy was misleading: the three editable Ground
layers looked like passive status labels, while the transcript looked like the
primary artifact. It also made a long Goal, Rule, or Case inaccessible rather
than merely compact.

The revised layout presents Goal, Contexts, Rules, Cases, and Dialogue as five
peer workbench components. They receive approximately equal vertical weight
after the composer and footer have been allocated space, and each component
has its own focusable, independently scrollable viewport:

```text
┌─ GOAL ────────────────────────────────────────────────┐
│ (not yet stated)                                  ▐   │
└───────────────────────────────────────────────────────┘
┌─ CONTEXTS ────────────────────────────────────────────┐
│ (not bound; not inferred)                         ▐   │
└───────────────────────────────────────────────────────┘
┌─ RULES ───────────────────────────────────────────────┐
│ (none yet)                                        ▐   │
└───────────────────────────────────────────────────────┘
┌─ CASES ───────────────────────────────────────────────┐
│ (none yet)                                        ▐   │
└───────────────────────────────────────────────────────┘
┌─ DIALOGUE ────────────────────────────────────────────┐
│ What are you trying to understand, decide, or make?▐  │
└───────────────────────────────────────────────────────┘
┌─ MESSAGE ─────────────────────────────────────────────┐
│ >                                                     │
└───────────────────────────────────────────────────────┘
```

Equal weight does not mean equal semantic importance or an exact pixel
guarantee. It prevents one layer from permanently taking the screen while
letting all five regions expand or contract with terminal height. Ground uses
a three-row pane minimum so the five panes and composer still fit a
conventional 24-row terminal; the shared primitive's default remains
unchanged for other commands. `Tab` and `Shift-Tab` move focus among the five
viewports and the message composer. Arrow and page-navigation keys scroll the
focused read-only viewport; when the
composer has focus, its normal editing keys remain local to the editor. The
bordered composer is a distinct action region, not a sixth workbench
component. Its box makes the typing boundary recognizable to users familiar
with conversation-first terminal agents and prevents a blank prompt from
looking like ordinary shell output.

`CONTEXTS` is a visible workbench frame, not a fourth semantic result layer
beside Goal–Rules–Cases. Blank and unbound Grounds state that no Context was
bound or inferred. A bound Ground renders only recorded role, name, and
binding-time direct-item counts for raw evidence, working candidates,
publication target, and placement targets. It does not load live Context
content, expose UIDs or digests, or claim current freshness; the normal
mutation boundary rechecks freshness later.

Within Ground, `Enter` sends, `Ctrl-J` inserts a newline, and `Escape`
immediately cancels or closes the TUI even when the composer contains an
unsent draft. That draft is not interpreted or persisted. Ground deliberately
does not also bind `Alt-Enter`: terminal applications commonly encode it as an
Escape-prefixed Enter sequence, which would make a lone Escape wait or fail to
provide the predictable exit requested by the user.

When an exact command is awaiting approval, the command/effect receipt and
its operation-specific approval keys take precedence over message entry. The
five workbench components remain inspectable, but changing focus or scrolling
must not edit, replace, or implicitly approve the frozen command. Returning
to dialogue requires an explicit refine/cancel action; approval remains bound
to the exact displayed argv.

This is the normal entry point when the person has only a rough concern, such
as wanting to work out which parts of some notes were reported. Early
grounding should not require a session identifier, polished Goal, Rules, or
Cases. The person can answer in ordinary language; the Codex-backed adapter
then returns either one consequential `ASK` turn or a structured
`PROPOSE(name, goal, completion)` turn. The provider never supplies a command.
The host validates and freezes those three fields, constructs the exact
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

### Future design: discovering Contexts from no Ground

The blank entry currently establishes only a Goal and portable Ground name.
Its `CONTEXTS` pane intentionally does not discover or bind Contexts. The next
design slice
should help a person who starts with an outcome such as “build the Task 1
campus wiki fixture” without making terminal location into hidden evidence.

The proposed guidance sequence is:

```text
describe the desired outcome
→ restate and approve a provisional Goal
→ explicitly open a local Context picker
→ show metadata-only candidates
→ assign each selected Context an explicit role
→ review one exact binding command and its effects
→ bind only after approval
```

Context discovery must be a local host operation, not an unrestricted provider
search. Before selection it may expose public Context names, access class
(ordinary writable, local fork, or query-only), and non-content locator
metadata needed to distinguish ordinary local candidates. Direct-item counts
may be shown for those ordinary local Contexts. A query-only candidate exposes
only its already-public name and access class; even its count is not inferred
by opening the source. Discovery must not load Memory content, traverse a
`context_ref`, open query-only sources, or send the store-wide candidate list
to the blank-entry provider. A candidate name is a suggestion, not permission
to inspect or bind it.

The picker should ask the person to assign roles rather than merely check a
set of Contexts:

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

After role assignment the host constructs one exact `mem ground` binding argv
locally, states which frames will be fingerprinted and saved, and waits for
the existing dedicated approval action. No Context is inferred from the
current directory, current active Context, name similarity, recency, or the
provisional Goal. This keeps a helpful “start from nothing” path compatible
with the existing privacy, multi-Context, and one-command approval
boundaries. Search ranking, metadata fields, and the picker interaction itself
remain future work.

The current provider is the existing one-shot Codex adapter authenticated by
the local ChatGPT login. Each interpretation is ephemeral and receives only
the submitted user turns. It does not receive the current Context, any
Memory, query-only content, existing Grounds, filesystem state, or command
authority. `ASK` turns accumulate the bounded user replies explicitly rather
than relying on hidden provider conversation state. Claude, MCP, or an
internal provider can later implement the same structured boundary.

On a proposal, the TUI shows the locally rendered command and lists every
effect: one Ground is created, its Goal and completion criterion are set, and
Rules, Cases, Contexts, Memories, and checkpoints are unchanged. Only the
dedicated `A` action approves that exact frozen proposal. `E` returns it for
refinement, while `Q`, Escape, Ctrl-C, provider failure, malformed output, or
name collision leave state unchanged. The approved argv is dispatched through
the ordinary `memcommit.cli` entry point as an argument vector, never through
a shell, and its actual output is reported after the TUI closes.

The original blank-entry slice ended after creating or cancelling one initial
Ground. The continuing vertical slice now enters the named-Ground TUI
immediately after creation and also opens that TUI when an existing name is
entered without options in a terminal. The five-component view
changes from `NEW · NOT SAVED` to `SAVED · UNBOUND`, then to `SAVED · BOUND`
after an explicitly approved binding command.

The continuing loop supports one exact command at a time for binding, Goal
revision, Rule proposal, Rule/Case review, and traceable Case proposal.
Proposal and acceptance remain separate approvals. After every success the
Ground is reloaded and the Goal, Contexts, Rules, Cases, and Dialogue
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

The named provider payload contains the portable Ground name, Goal and
completion text, Rule/Case text and rationale, their local `rN`/`cN` aliases
and relations, state and revision, bound Context names, and the current visible
dialogue cycle. It does not contain live Context projections, source
references, or durable UIDs. A saved Case's text may be an earlier exact copy
of source Memory content, but its source identity remains local. A source
selector typed for a new Case is matched locally and replaced with a stable
`mN` alias before inference; only an alias actually introduced by that
redaction can be mapped back into the reviewed command.

Natural-language transcript persistence and asynchronous provider progress
remain follow-up work. Non-TTY output remains deterministic so remote
captures, tests, and surrounding agents do not hang on a terminal prompt.
The bordered multiline message composer has been extracted as state-free
terminal chrome and is also used by meld. Ground still owns its ASK/PROPOSE
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
output until focused Rule and Case receipts are designed; `--focus-target`
currently rejects those combinations rather than hiding the affected item
behind aggregate counts.

In this prototype the person may answer in the blank-entry TUI, continue in
the named-Ground TUI, or work through a surrounding agent conversation. The
relevant adapter maps that answer to at most one existing state-changing
`mem` command, displays the exact command and its Goal, Rules, or Cases effect,
and waits for explicit approval. One approval authorizes only that command.
The adapter may then run it through the ordinary CLI path and must obtain
separate approval before a follow-up command. Commands proven to be read-only
do not consume this approval. In particular, focus rendering of an existing
Ground is read-only; the legacy `mem ground NAME --snapshot` form is
creation-capable when `NAME` does not exist and must not be treated as
inspection until existence has been confirmed.

This split is intentional:

- `ground` stores and validates the jointly revised Goal, Rules, and Cases;
- the agent interprets natural-language turns and selects one deterministic
  CLI action;
- existing commands remain the mutation boundary; and
- Context changes continue to use `add`, `edit`, `update`, or another
  purpose-specific operation rather than direct JSON edits by `ground`.

The current slice adds a semantic interpretation adapter, not a second
persistence engine. It does not persist natural-language dialogue turns or
batch multiple mutations into one approval. Starting with one real command per
turn lets the design acquire missing Goal/Rule/Case primitives from observed
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

### Generalization target: Goal–Rules–Cases alignment

`mem ground` should generalize the conversational pattern proven by atomize:
the person and agent use consequential follow-up questions to align three
revisable layers rather than treating the first request as a fixed form.

| Layer | Grounding role |
| --- | --- |
| `GOAL` | The desired outcome and completion criterion: what the session is trying to make true. |
| `RULES` | Inspectable, revisable rules for interpreting evidence, making judgments, proposing actions, and deciding what the current operation may apply. |
| `CASES` | Concrete judgments about exact artifacts. Proposed Cases test the current Goal and rules; explicitly approved Cases become regression anchors. |

These three layers are the Ground's result, jointly revised by the person and
agent. `ground` does not produce a separate result artifact. A later
purpose-specific operation may use the accepted Ground to propose changes to a
Context, but that Context is not a fourth Ground layer.

`Goal`, `Rules`, and `Cases` are stable type names. Whether they have become
shared or remain provisional belongs in item and session status, not in names
such as `Shared Goal` or `Working Rules`. The serialized field
`contract_name` remains an internal version-1/version-2 compatibility name;
new user-facing output calls the artifact a named Ground.

The artifact and the Case are related but not identical. In atomize, Memories
are the concrete artifacts being judged. A Case records the expected reading,
judgment, or outcome for an exact Memory or group of Memories. Merely being
inspected, affected, or edited does not make a Memory a golden Case; that
accepted status requires explicit approval.

A difficult Case can reveal that a Rule or even the Goal is wrong.
Grounding is therefore bidirectional rather than a one-way process of fitting
examples to an immutable specification. Its reusable dialogue should be:

```text
show a concrete mismatch or candidate
→ ask a follow-up whose answer could change a Goal, rule, Case judgment,
  or downstream action
→ restate the agent's provisional understanding and its consequences
→ let the user confirm, extend, correct, retract, defer, or add exact context
→ revise the affected layer and recheck dependent Cases
→ request explicit approval before canonicalization or mutation
```

Follow-ups must be consequential. A generic request for more detail is not
enough; the interface should say which judgment or proposed action cannot be
settled without the answer. The user may choose a suggested reading, enter a
different reading, revise a Rule, add a closer Case, or revise the Goal
when lower-level evidence exposes a bad Goal boundary.

The first two representative applications are fixed as follows.

1. **Atomize ambiguity resolution.** The Goal is to reduce actionable
   ambiguity until the selected reading and consequential Memory changes match
   the reviewer's intent, not to eliminate every imaginable linguistic
   reading. Rules describe how the agent may judge readings, propagate
   supplied context, identify affected Memories, and propose or apply edits.
   The source and affected Memories are the concrete artifacts; reviewed
   readings and expected outcomes are the candidate Cases. A clarification
   may resolve one Memory, expose a downstream Memory that must change, or
   reveal that the agent's scope extension is wrong.
2. **Task fixture and wiki co-design.** The Goal is to agree on what the
   campus wiki and local construction-update fixture must represent and where
   each Memory belongs. Rules describe evidence requirements,
   categories, placement, coverage, non-invention, and audience or disclosure
   judgments within the fixed privacy boundary. Cases bind source examples to
   expected fixture content, placement, or disposition. A follow-up may add a
   missing Case, refine a rule, or reveal that the original Goal was
   incomplete; accepted Cases become regression anchors for later candidates.

These two examples are the initial design targets, not an exhaustive operation
list. The current provider-backed adapter uses existing deterministic Ground
commands for revision and approval. Any later asynchronous or cross-operation
dialogue controller must preserve the same one-command permission and
application boundaries.

Rules are adjustable task knowledge, not a way to negotiate away
implementation invariants. Privacy restrictions, query-only opacity,
provenance requirements, stale-frame validation, and explicit mutation
authority remain hard system boundaries. Interpreting atomize through
Goal–Rules–Cases also does not convert an atomize session into a named
ground, promote an affected Memory into a golden Case, or synchronize the two
schemas. Any transfer requires a separate explicit provenance and
compatibility contract.

## Decision

`ground` is the session-level operation for a person and an agent to establish
and maintain a local Goal–Rules–Cases Ground. The Ground itself is the jointly
produced result. It grows through concrete cases, readable rules, corrections,
boundary examples, and explicit decisions.

The long-term loop is:

```text
present one concrete case
→ judge it against the currently accepted Ground
→ retrieve a supporting case and a materially close contrast
→ apply the Rules, curate a Case, or induct a Rule delta
→ show the rule and case diff
→ let the user accept, correct, supply context, or enter a closer case
→ regression-check previously accepted cases
→ repeat
```

Retrieval of supporting and contrast cases, semantic regression, and
whole-Ground approval are not yet automated.

The operation is complete only locally: reviewed cases in the named scope are
adequately explained, unresolved boundaries remain explicit, regression checks
pass, and the user explicitly approves the Ground. Neither the model nor a
count threshold may infer approval.

## Operation hierarchy

The discussion originally gave `induct` too much responsibility. The revised
hierarchy is:

| Concept | Responsibility |
| --- | --- |
| `ground` | Persist and validate Goal–Rules–Cases judgments through deterministic actions used by the conversational orchestrator. |
| coverage check | Judge whether the current Rules and accepted Cases already explain a candidate. This is a stage, not a new public `fit` command. |
| `induct` | Propose a reusable rule, exception, narrowing, or broadening from reviewed cases. |
| case curation | Find, enter, or retain fit, boundary, and contrast cases. It is initially an internal grounding action rather than a public command. |
| regression check | Show whether a proposed rule or case decision changes previously accepted judgments. |
| `fill` | Use an established requirement/evidence Ground to propose missing target content. |
| `dream` | Perform background discovery or consolidation; it may enqueue a grounding candidate but cannot approve it. |
| `review` | Provide a reusable interaction surface for an already defined finding adapter; it is not the semantic grounding process. |

The earlier `fit` notes use `YES / MAY / NO` for whether Memories fit together
inside a Context. Reusing the public name for case-to-rule coverage would make
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
  shared, inspectable local Ground for interpreting and judging Cases.

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
terminals or agents. The named form is intentionally create-or-resume, so
`--snapshot` also creates an empty Ground when the supplied name does not
exist. A mistyped name can therefore create an extra empty file; listing,
renaming, and archiving named Grounds remain future CLI work.

## Schema

Version 1 saves:

- a canonical session UUID;
- portable Ground name;
- goal and completion criterion;
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

Version 2 is introduced only by explicit frame binding. It additionally saves:

- a copied, content-digested source brief;
- exact raw, derived, publication-target, and placement-target Context frames;
- an editable Goal and editable per-target requirements;
- proposed or reviewed rules, cases, and decisions;
- structured source-Memory and target-Context references;
- a rule provenance of `USER_STATED`, `DISTILLED_FROM_GOAL`,
  `INDUCED_FROM_CASES`, or `JOINTLY_REVISED`; and
- one durable candidate cursor.

Version 1 remains fail-closed and is never silently reinterpreted as version
2. A saved rule/case proposal and a review decision each advance the semantic
revision exactly once. Moving the cursor does not.

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
a Case destination.

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
   top-down from the Goal, induced bottom-up from cases, stated by the user,
   or jointly revised; and
3. `CASES — FIT / BOUNDARY / CONTRAST`: proposed or reviewed examples that
   fit or challenge the current rules. Only explicitly accepted cases are
   golden regression anchors.

The copied Task description is displayed above these layers as a fixed source
brief. It is evidence about why the workbench exists, not the entire editable
Ground. Target-specific success criteria are displayed inside the Goal layer,
not as a fourth semantic layer. The Goal and those criteria may change when
lower cases expose a poor category, impossible requirement, or missing
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
- Rules and accepted golden Cases that justify coverage; and
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
| `EMPTY` | No accepted `INCLUDE` Case backed by an accepted Rule satisfies the slot. |
| `PARTIAL` | Some such distinct source cases satisfy the slot, but the recorded minimum is not met. |
| `COVERED` | The recorded minimum is met by accepted `INCLUDE` Cases backed by accepted Rules, counting each source Memory once per target. |
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
content-addresses each case to exactly one Memory in the working-candidate
Context. It does **not** yet persist the candidate-to-raw span mapping, so the
snapshot does not claim to show a raw trace. The workbench can select a
candidate, propose targets and expected wording, attach it to an existing
Rule, and accept, refine, defer, or reject it. `REFINE` currently
changes rule wording or a case's expected output; changing a case's targets,
role, disposition, rationale, or raw provenance remains follow-up work. A
proposed placement may name `participant/campus-wiki-fork`, one of the six
local slots, or both when their distinct source-of-change and materialization
roles justify the duplication. It may not name the query-only `campus-wiki`
origin.

The upper Ground must not be mixed into the lower candidate list. The top
answers “what are we trying to achieve, what rules currently express it, and
which reviewed cases support those rules?” The bottom answers “what evidence
and derived candidates can justify or revise a particular target decision?”

This is deliberately bidirectional. A Goal or rule may suggest how to judge a
lower case, while a stubborn or awkward lower case may justify revising the
rule or even the Goal. An accepted rule can be refined and reopened. Because
only accepted rules support coverage, its accepted cases stop contributing to
`COVERED` until the revised rule is accepted again. A Goal or target-criterion
revision is recorded with a reason, but automatic semantic regression of
prior cases remains follow-up work.

## Proposed cases, golden cases, and the first review round

An agent-produced Case is `PROPOSED`. It has no accepted authority, does
not count toward `COVERED`, and is not a regression anchor. A **golden case**
is the user-approved form of a concrete judgment: its evidence trace, target
slot, expected target content or disposition, and rationale have all been
reviewed. Golden cases may be tagged as fit, boundary, or contrast evidence,
but the tag does not replace explicit approval.

The implemented deterministic slice supports the following recorded actions:

```text
select one of the 54 bound working candidates
→ show its wording and candidate UID/digest
→ propose a Rule alone, or attach a Case to an existing Rule
→ propose target Contexts, expected wording, disposition, and rationale
→ let the user accept, refine expected wording, defer, or reject
→ save that decision only in the named ground session
→ recalculate target status from accepted INCLUDE cases and accepted rules
```

If the user refines the proposed expected output, the revised proposal must be
accepted before it may become a golden case. A deferred case becomes
`DEFERRED` and does not improve target coverage. Missing-context entry,
target/disposition correction, and automatic regression reporting are not yet
part of the case-review action; a target criterion can instead be revised
explicitly with a recorded reason.

This vertical slice establishes one bound candidate, one content-addressed
candidate reference, one target decision, one explicit approval boundary, and
one derived status change. It deliberately does not claim a raw trace or
semantic regression result. Subsequent fixture work should establish at least
one approved seed case for each coverable target slot rather than assuming
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

- be promoted to a golden case;
- change a slot to `COVERED`;
- approve the Ground; or
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

COMPLETION
  The reviewed cases in the current scope are adequately explained ...

SCOPE  participant/campus-wiki-fork, participant/construction-updates
RULES 0 · CASES 0 · UNRESOLVED 0 · DECISIONS 0

No grounding material has been recorded.
The session is ready for jointly reviewed rules and cases.
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
  review command can mark a Rule or Case accepted.

This non-mutation boundary remains in force for the implemented workbench.
Reviewing a placement, promoting a proposal to a golden case, changing an
upper-region status, or even marking the Ground `GROUNDED` changes only the
named Ground artifact. It must not add, edit, or delete a Memory in
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
boundaries, at least one accepted rule or case, and a regression report for
the approved revision. A provider cannot set this status by itself.

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
concrete placement or content case, show its raw trace plus the nearest
supporting and contrast cases, then let the user:

- apply the current Rules;
- correct the proposed judgment;
- refine or add a rule;
- retain the case as fit, boundary, or contrast evidence;
- enter a closer case or missing context; or
- defer the candidate.

The current deterministic slice records rules, cases, candidate-level
references, and explicit decisions. Raw trace retrieval, nearest-case
retrieval, automatic batch generation, and whole-Ground approval remain
future work.

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
- Importance ordering, creation-time ordering, affected-decision estimates,
  automatic batch generation, inherited or predecessor Context handling, and
  integrated ambiguity/conflict resolution remain deferred. The first
  user-study slice may preserve the original Memory order.
- Frame digests currently cover the store-loaded projection, not a separate
  raw serialized pointer ledger; unresolved `context_ref` detection is
  deferred to a reference-aware binding version.

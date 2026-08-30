# Shared TUI Chrome and Exact-Command Review

> **Ground compatibility note (2026-08-29).** The named JSON Ground shell and
> its exact-command review path described in the Ground-specific sections below
> have been removed with `GroundSession`. The shared TUI primitives remain in
> use by other operations, while physical Ground uses its workspace shell and
> ordinary Context-backed commands. The old Ground detail is historical
> rationale, not a current interface contract.

## Problem

Several memcommit operations use full-screen terminal interaction, but they do
not share one semantic or persistence model:

- `ground` maintains a Goal, Rules, Ground Memories, and explicit review
  decisions;
- `meld` maintains a relation ledger, issues, readings, and staged proposals;
- finder results become interactive through `mem review`, whose responses are
  autosaved but do not apply Memory changes; and
- `atomize` has typed source findings and its own drill-down navigation.

They nevertheless repeat presentation mechanics: terminal-safe text,
interactive-terminal checks, independently scrollable regions, viewport
anchors, framed input panels, focus traversal, footers, and full-screen
application setup. Ground also needs a stronger mutation boundary: one exact
locally constructed command must remain visible and may run at most once after
a dedicated approval.

## Decision

Reuse terminal mechanics and approval receipts, not a generic semantic
session.

The neutral layer contains:

1. `safe_terminal_text`, interactive-terminal validation, viewport anchoring,
   and slot-based vertical TUI composition;
2. state-free framed read panes, independently named multiline `TextArea`
   buffers, a standalone framed composer, and an in-frame manager that can
   mount one buffer below a pane's read viewport;
3. a state-free hierarchical Escape dispatcher that asks operation-owned
   callbacks to retreat one visible layer before delegating final closure;
4. an immutable `CommandReview` holding only an argv tuple and effect
   lines; and
5. deterministic rendering of injectively display-escaped arguments with
   `shlex.join`.

`CommandReview` is owned by
`memcommit.adapters.console.terminal.components.command_editor.model`.
The same flat `command_editor` package owns form, control, rendering,
interaction, and standalone approval mechanics. Controls project an exact
command, and a complete edited command projects atomically back into controls.
Operation-specific START and TURN builders and endpoint decoders live beside
Meld, Update, Sever, and Branch because only those adapters know their public
grammar and upper-field meaning. This placement matters even though the value
is small: every command screen must approve the same immutable identity
without making the neutral terminal component import operation code.

The focused final-review action uses `Enter` as its canonical approval key.
The shared interaction helper binds that gesture and retains case-insensitive
`A` only as a compatibility alias for already published shells.  Ground keeps
`Enter` narrower than that legacy alias: it approves only while the visible
Chat receipt owns focus, so inspecting another pane and pressing `Enter` cannot
run the frozen command.  The helper does not own application semantics.  Each
operation still validates its typed plan, defines the approval callback, and
decides whether the reviewed argv is executed or only documents an equivalent
typed mutation.

The shared message composer does not bind keys or interpret text. Blank and
named Ground mount its buffer inside the active semantic pane; meld retains
the standalone bordered form. Their adapters still decide when it receives
focus, what Enter means in each surrounding view, which provider is called,
and what is persisted. In a focused Ground input field, `Enter` sends,
`Ctrl-J` inserts a newline, and `Escape` collapses without submitting the
draft. Ground does not bind `Alt-Enter` because
many terminals encode it as an Escape-prefixed Enter sequence. Meld retains
its `Ctrl-S` compatibility submission alias, but it also reserves a lone
`Escape` for immediate back-or-close behavior and therefore uses only `Ctrl-J`
for multiline input. The shared composer itself binds none of these keys.

The Escape dispatcher is deliberately not a global keymap or a generic
`Application.exit`. It evaluates operation-supplied, deepest-first callbacks
and invalidates the screen after the first callback that consumes the key. If
no visible presentation layer can retreat, it invokes an operation-owned close
callback. This makes the interaction grammar reusable without bypassing
Ground's asynchronous cancellation guard, Find's in-flight close request, or
another operation's persistence result. Adoption remains explicit and tested
per shell.

The display escape is part of the approval contract. Newlines, tabs,
backslashes, terminal controls, bidi controls, zero-width format characters,
and Unicode line separators are rendered as visible escapes inside command
arguments and effect lines. This prevents untrusted text from drawing a fake
second command or trusted heading. The displayed representation remains
unambiguous, while execution still uses the original frozen argv directly and
never reparses the display text.

Operation adapters retain:

- their provider schema and prompt;
- their state, item identities, and evidence contract;
- the meaning of Enter, arrows, choices, and comments;
- persistence and cancellation behavior; and
- construction and validation of any exact argv.

The provider never returns command authority. It returns typed domain fields.
The operation adapter validates those fields against local state, freezes one
argv and its complete effects, and only then passes the receipt to the shared
review component. Ground-specific concurrency fields, such as the expected
Ground identity, revision, and digest, remain typed fields on the Ground
proposal. Their guard token is carried opaquely inside the frozen argv, but
the operation-neutral receipt neither parses nor assigns meaning to it.

## Ground vertical slice

The blank Ground TUI creates only a named schema-version-1 scaffold. That
scaffold is intentionally unbound: the existing Ground engine does not permit
Goal revision, Rule proposal, or Ground Memory proposal until exact evidence
and target Context frames have been bound.

The continuing named-Ground TUI therefore follows the engine's existing
sequence:

```text
create named Ground
→ show WORKING · SAVED · UNBOUND
→ ask for explicit Task/raw/derived/publication-target names
→ approve one exact binding command
→ show WORKING · SAVED · BOUND
→ propose one Rule
→ separately review that proposed Rule
→ propose one traceable Ground Memory from a bound candidate Context Memory
→ separately review that proposed Ground Memory
```

The first implementation used a seven-row upper summary for Goal, Rules, and
Ground Memories and gave the remaining body to Chat. The first realistic
run showed that this made three editable Ground layers look subordinate and
prevented a long item from being inspected in place. Ground now composes five
peer workbench components—Goal, Contexts, Rules, Memories, and Chat. Each
owns a focusable scroll viewport, so growth never makes content inaccessible.
Semantic peers are not forced to reserve equal blank space: newly authored
Goals are capped at 40 words and their frame at three visible body rows, while
Contexts prefers five visible body rows (and compresses to one when necessary),
while Rules, Memories, and Chat share the remaining flexible height.
Contexts receives that preference because the first-turn picker may need to
show Current, Main, alternatives, a possible uncreated Context, and evidence
boundaries together. It is the visible evidence-and-target frame, not another
semantic result layer beside Goal–Rules–Memories. Chat contains the general
Message composer inside its own outer frame. Entering another Ground pane
moves the same buffer into that pane, so it remains an in-component dialogue
rather than a separately bordered sixth workbench region.

Within Ground, Chat is the whole-Ground conversational orchestrator. A
pane-local comment carries its focused referent into that conversation but may
lead the agent to propose a change in another Ground layer; focus is not a
semantic effect boundary. Direct edits remain exact replacements of their
selected targets, and every proposed cross-layer consequence retains Ground's
one-command, explicit-approval boundary.

The blank Ground Context picker may hold more than one name-only suggestion.
`Space` toggles candidates, selection order makes the first checked name the
local Main, `F` finishes or reopens the plan, and `N` edits an exact new name.
`Enter` opens the Context-focused conversation. Once finished, the pane hides
unselected alternatives so reviewed choices remain legible. These names are
process-local hints only: they neither load nor bind Contexts, enter provider
input, nor persist in the Ground. Explicit frame binding remains a later,
separately approved command.

`Tab` and `Shift-Tab` traverse the five panes and composer. Navigation keys
scroll the focused read-only pane, while editing keys stay local when the
composer has focus. During exact-command review, the receipt and its dedicated
approval/refinement/cancellation actions temporarily own the consequential
key boundary. Pane focus may change for inspection, but it cannot mutate or
implicitly approve the frozen argv.

An exact UUID in a review command is not enough for informed approval. The
Ground adapter therefore augments the neutral effect block with the selected
alias, item kind, current status and wording, and action-specific semantics.
In particular, Rule `REFINE` replaces Rule content and changes provenance to
`JOINTLY_REVISED`, whereas Ground Memory `REFINE` replaces only expected
output while preserving the source, linked Rule, role, disposition, and
targets. Proposal receipts similarly name the prospective `rN` or `cN`,
provenance or classification, exact locally resolved source Context Memory,
linked Rule, targets, and expected output.

The Action frame is content-sized instead of inheriting a flexible pane
height. Approval uses two body rows; interpretation and apply errors use one.
The exact command and effects remain in Chat, so reducing empty Action
rows does not reduce the reviewed information or approval boundary.

Each approval applies exactly one normal CLI argv through
`python -m memcommit.adapters.console.entrypoint`; it never invokes a shell and
never writes Ground JSON directly. After success, the controller reloads the named Ground and
updates all affected component panes. Proposal and semantic acceptance are
deliberately different commands. Pressing `Enter` on a focused reviewed Rule
proposal permits
recording a `PROPOSED` Rule; it does not mean the Rule is accepted.

The reviewed argv contains an opaque `--if-ground-version` token that freezes
the Ground UID, revision, and canonical serialized-state digest. Revision
alone is insufficient because binding can change a revision-zero scaffold
without incrementing its semantic revision. The adapter performs an early
comparison for useful feedback, and the ordinary CLI repeats the comparison
at the actual save boundary while holding a per-Ground process lock. For a
bound Ground, it first locks and rechecks every bound Context frame, then
takes the Ground lock and performs the compare-and-swap. A concurrent Ground
or bound-Context change therefore rejects the command before replacement
rather than letting the reviewed command act on newer evidence.
Ordinary non-replacement `mem ground NAME ...` writers automatically compare
against the Ground record they originally loaded as well. This matters because
a stale ordinary writer must not be able to overwrite a newer guarded TUI
mutation merely by omitting the hidden token.
Because an unbound Ground has no saved frames yet, a binding receipt also
contains one opaque `--if-context-version` token for every reviewed raw,
derived, and target Context. The child CLI requires the frames it loaded to
match those tokens before entering the locked verification and save path.
Here “opaque” means opaque to the shared presentation component, not secret:
the displayed guards contain local Ground or Context identity/version data,
digests, and counts. A Ground Memory argv can likewise display its locally
resolved source UID. None of those locally constructed receipt fields are
added to the provider payload.

The shell reloads durable Ground state before interpreting a new turn and
again after an unconfirmed application. It never automatically retries the
same approval. This mirrors the project's grounding model: a changed shared
state requires a fresh interpretation and a fresh, visible command.

## Information boundary

The blank TUI still sends only submitted text to the provider. Once the Ground
has a name, the named-turn provider receives only:

- the portable Ground name;
- saved Goal;
- saved Rule and Ground Memory text with local aliases such as `r1` and `c1`;
- Rule rationale, provenance, and linked Ground Memory aliases, plus each
  Ground Memory's rationale, linked Rule alias, role, disposition, target
  Context names, and expected output;
- Ground state and revision;
- bound candidate and target Context **names**; and
- the submitted dialogue text plus the provider's own visible understanding
  and question from the current unresolved turn cycle.

It does not receive a live Context projection, source references, durable
Ground/Context/Memory UIDs, filesystem paths, query-only material,
current-Context state, or command authority. Saved Ground Memory content is
part of the Ground payload and may itself be an earlier exact copy of source
Context Memory text; the provider is not given the corresponding source
identity. For a new Ground Memory, the person must supply a source Context
Memory selector. Before inference, the host matches that selector locally
against the bound candidate Context and replaces it throughout the unresolved
dialogue with a stable local alias such as `m1`. The provider may return only
an alias actually introduced by that local redaction. The host then maps it
back and freezes the full UID only in the reviewed CLI argv. Ambiguous
selectors and invented aliases fail closed. Other command-looking dialogue
remains untrusted provider data rather than executable authority.

The repeated provider calls are otherwise stateless. Carrying the visible
question forward prevents a short answer such as “that one” or “yes” from
losing the exact question it answered, without relying on hidden provider
conversation state. The cycle is cleared after an approved command reloads the
Ground.

## Why Ground keymaps and semantic persistence remain local

The same key cannot be given one cross-operation meaning:

- Enter opens the focused Ground pane's conversation, or sends when its
  embedded field is focused;
- Enter expands a meld issue when its list is focused, but sends text when its
  shared dialogue editor is focused;
- Enter focuses the response editor in review; and
- atomize uses it for issue drill-down and choice behavior.

Persistence is equally different. Ground is unchanged until exact approval;
Atomize saves workbench responses; Meld's outer controller owns provider calls
and staged application; Update owns its multi-Context plan and receipt. A
generic durable session would hide these differences and weaken the state
boundary.

The shared frame is therefore slot-based. Each operation supplies its own
header/state panes, body panes, action region, keymap, and footer. A neutral
pane primitive may provide a title, viewport, scroll margin, focus style, and
relative height without knowing whether its content is a Goal, a meld issue,
or a finder result. Ground composes five such panes because its Goal, Contexts,
Rules, Memories, and Chat must remain simultaneously inspectable.

Focused Frames use actual heavy box-drawing glyphs (`┏━┓┃┗┛`) in addition to
the shared light-blue bold style; unfocused Frames retain the ordinary light
glyphs (`┌─┐│└┘`). Bold styling alone is not a sufficient focus cue because
terminal fonts do not consistently increase the stroke weight of box-drawing
characters. The common binding changes only Frame chrome and never traverses
the dynamic body, so semantic content and nested controls remain unchanged.

Ground and meld share the same state-free Message buffer primitive, while
Ground additionally uses the reusable in-frame manager and Meld retains a
standalone frame. Review and atomize keep their operation-specific editors.
Meld, review, or a future interactive finder may reuse these presentation primitives
where their own design calls for several visible components. That reuse does
not grant them Ground's five-pane layout, aliases, key meanings, provider
payload, approval semantics, or persistence model. Sharing component chrome
while keeping operation adapters semantic is the boundary that permits later
reuse without inventing a generic workbench state.

Meld and Atomize now additionally use `ResolutionWorkbench` for the narrower
list/detail/option/comment grammar, and Update projects read-only planned
changes into it. This does not contradict the local semantic boundary: the
shared asset is an immutable view, UID-bound action envelope, and ephemeral
navigation controller, not a provider schema, persistence model, readiness
rule, or application engine. Ground remains outside that higher-level asset.
See
[`semantic-resolution-workbench-design-rationale.md`](semantic-resolution-workbench-design-rationale.md).

## Alternatives rejected

### A generic provider-returned command

Rejected because provider text would become executable authority and because
operation-specific validation, privacy, and effects could be bypassed.

### A single generic durable semantic workbench

Rejected because Goal–Rules–Memories, Meld relations, finder findings, Atomize
issues, and Update plans have different evidence requirements, approval
semantics, and persistence timing. Sharing an immutable resolution projection
and interaction grammar does not merge those semantic artifacts.

### Allow Rules before binding

Rejected for this slice because it would silently overturn the existing
Ground invariant that Rules and Ground Memories are judged against explicit evidence
frames. A future general-purpose unbound Ground schema would require an
explicit versioned data-model decision rather than TUI wiring.

### Automatically bind the current Context

Rejected because it would make terminal location an implicit evidence
decision, conflict with multi-Context Ground work, and transmit or persist
state the person did not approve.

### One compact Ground summary above a dominant Chat panel

Rejected after the realistic Ground run. It conserved rows, but it made Goal,
Rules, and Memories appear to be passive status while Chat occupied most
of the screen. Truncating those layers also made “always visible” mean “not
actually inspectable.” Independent viewports preserve the five-component
workbench; the later three-line Goal cap is a content-specific allocation,
not a return to one dominant transcript.

## Current limitations

- Existing consumers may still import either compatibility path.  They already
  receive the one neutral value type, so this is a dependency-cleanup concern
  rather than a behavioral split.  New internal code should import the neutral
  owner directly; terminal rendering should import the TUI component.
- Provider calls are synchronous inside the prompt-toolkit handler, so a slow
  semantic turn can temporarily stop repainting. A reusable progress state
  should later move provider work into an outer controller or async task.
- Natural-language dialogue transcripts are ephemeral. Saved Ground items and
  decisions persist, but the natural-language exchange does not.
- Whole-Ground agreement is not yet durable. Closing the TUI only closes the
  view; a future agreement action must bind approval to one reviewed revision
  rather than to a separate completion sentence.
- A Ground Memory still requires the person to supply a candidate Context
  Memory selector, which is converted to a provider-safe local alias.
  The TUI has no local read-only candidate picker yet; provider access remains
  deliberately insufficient to invent or inspect that selector.
- Equal pane weight is approximate because the composer, footer, borders, and
  minimum title rows consume fixed height. On a very small terminal, all five
  panes remain distinct but may show only one or two content rows at a time;
  independent scrolling preserves access, not simultaneous visibility of all
  content. Responsive pane collapsing and a user-controlled pane maximizer
  remain follow-up work.
- A hard display guarantee for a maximum-length argv still requires a
  dedicated scrollable command-only panel or tighter field limits. The
  approval receipt must never be silently truncated into apparent completeness.
- Static `mem find-*` output does not become interactive merely by sharing
  chrome. Its interactive route remains `mem review`; each finder needs an
  explicit adapter before it can adopt additional dialogue behavior.

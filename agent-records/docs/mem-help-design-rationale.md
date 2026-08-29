# `mem help` design rationale

## Intent

The default Typer help output proves that a command is registered, but its
syntax-first layout is harder to scan as a complete command inventory. That
distinction matters while building the study prototype and when preparing its
printed cheat sheet.

`mem help` therefore renders one concise inventory line per visible registered
command. An exact hidden spelling may be folded into its canonical row when
both execute the same callback and contract. The interactive browser offers two
projections of the same audited metadata: `BY KIND` for intent-first discovery
and `A–Z` for exact-name lookup.
The stable non-TTY inventory remains case-insensitive A–Z for scripts and
captured study output:

```text
name [(exact spelling)] [(status)] - short description
```

It reports capabilities; it does not recommend a command sequence or perform
work for the participant. Source registration order remains free to group
related implementation code; neither Help projection depends on it.

## Console module ownership

The console adapter keeps Help's four responsibilities in focused sibling
modules. `inventory.py` owns the console taxonomy, command Forms, inventory
models, and validation against the registered CLI and application Operation
Help catalog. `rendering.py` owns plain, lookup, and prompt-toolkit text
projections. `selector.py` owns the interactive browser lifecycle, transient
selection state, focus topology, and key bindings. `command.py` remains the
thin top-level orchestration boundary for focused lookup, non-TTY dispatch,
selected-command handoff, full syntax Help, and session-Help backend wiring.

This is a physical ownership split, not a change to catalog meaning or the
terminal interaction contract. The original `command.py` import names remain
available as a temporary compatibility surface while production callers move
to the narrow owner. The first extraction deliberately leaves the large Form
catalog and the selector's closure-based state machine intact inside their new
modules: splitting those structures further without a separate behavior need
would increase ordering and focus-regression risk. A later change may divide
them behind the same module contracts.

## Natural-language focused lookup

Supplying one positional request changes only the discovery projection:

```text
mem help "compare two Contexts and find relevant Memories"
```

The command freezes the same complete public operation catalog, submits its
canonical selection fields plus the request to one bounded semantic turn, and
requires an ordered list of exactly three distinct operation names. The pinned
policy is `gpt-5.6-sol` with reasoning effort `none`. The model selects IDs
only; it cannot author the visible description, best-for text, explanation,
score, command form, or rationale.

Each validated candidate is rendered in semantic order as the existing
collapsed Help record, without an explicit ordinal label:

```text
mem compare ┬ Compare Memories in two Contexts and report what they share,
            │ what differs, and what appears only on one side.
            └ WHEN · Comparing two Contexts as a whole to understand where
                     they align and differ.
```

The first candidate is the strongest semantic fit. When fewer than three
operations directly satisfy the request, the second and third may be useful
adjacent alternatives or behavior contrasts. This fixed three-candidate frame
is deliberate study scaffolding: it keeps exposure cardinality constant and
can prompt a participant to consider actions beyond the most obvious match.
Even a weak, unrelated, or nonsensical nonblank request receives the three
closest catalog possibilities. Results carry no confidence, `WHY`, expanded
overview, forms, or execution action. The focused lookup exits after the three
rows; it does not open the full-screen browser, read a Store or Memory, or
execute any candidate. Every Profile's command-attempt ledger retains the
entered `mem help REQUEST` command. A current Study Participant additionally
records the normalized request and exact three-operation ranking as typed
events in its detailed Study action ledger; other Profiles retain no ranked
Help result.

Visible order is not randomized or counterbalanced. Semantic fitness and
display position therefore coincide intentionally, even though the interface
does not print ordinal labels. This keeps the interface and study condition
simple, but it means later analysis cannot separate semantic fitness from
primacy. Candidate selection by display position may be reported descriptively;
position bias is a recorded limitation rather than a separate experimental
manipulation.

Direct matching is semantic rather than a catalog-vocabulary gate. A short,
colloquial, metaphorical, or fragmentary request may match when its intended
effect is still distinguishable; it need not repeat `Memory`, `Context`, or the
authored Help wording. In particular, generic outcome language asking for an
answer-producing sentence or response may match `query`. Lexical overlap with
the catalog is therefore an evaluation-corpus provenance concern, not a reason
for the product lookup to reject an otherwise valid request.

The active Profile's immutable provenance narrows that rule during a live
`init-study` run. Before provider connection, focused Help freezes every
authored `DESCRIPTION` and `WHEN` value in all five supported Help languages,
normalizes Unicode, case, punctuation, underscores, and whitespace into exact
tokens, and measures the longest contiguous token sequence shared with the
request. If that exact run covers at least 50% of any one authored field, the
Study lookup exits with a stable original-wording error. It does not reveal the
matched operation, language, field, or score and does not connect a provider.

The 50% denominator is the authored field, not the request: the boundary asks
how much catalog copy was reused rather than how much ordinary task language
happened to use MemCommit terms. The threshold is inclusive, deterministic,
and has no fuzzy, embedding, semantic-similarity, stop-word, or human-review
stage. Consequently a reordering or paraphrase that breaks the contiguous exact
run is allowed; this is an intentional limitation of the requested exact-copy
criterion. Both participant and granted-memory Study roles are recognized by
validated `init-study` source provenance rather than mutable Profile names.
Bare Help and focused Help outside an active Study Profile retain their normal
behavior. The provenance check opens only the external Profile registry; it
does not open a Store, Context, or Memory.

Only the Participant role retains focused Help wording and results. The
granted-memory role receives the same Study-copy guard but does not retain
content-bearing Help actions.

Bare `mem help` remains the complete deterministic inventory below, in both its
plain and interactive forms. The semantic provider is connected only after a
nonblank positional request and complete-catalog preflight. Provider or decoder
failure publishes no partial rows. The whole catalog currently fits one call;
crossing that bound rejects the lookup until a tested global reranker exists,
rather than silently prefiltering operations and changing what the participant
could discover.

After that local preflight, a focused lookup in a TTY owns one transient
`MEM HELP · 1/1 · THINKING …` line on stderr from provider connection through
validated decoding. The line is cleared before the matched rows or an error is
published. It is a liveness signal for the bounded Help turn, not provider
reasoning or chain-of-thought. Bare `mem help`, Study-copy rejection, redirected
or non-TTY stderr remain free of the indicator so stable stdout and the
deterministic inventory do not change. The operation-neutral progress renderer
belongs to `interfaces.console.progress`; the former command-module path is an
import-only compatibility facade so the Help interface never depends outward
on a command adapter.

The ordered live PTY evidence in
[`agent-records/docs/screenshots/mem-help-natural-language-20260820`](screenshots/mem-help-natural-language-20260820/README.md)
records direct, multi-action, metaphorical, unrelated, and generic requests
against the real provider route. Each successful lookup displays three ranked
candidates. Every capture retains the raw terminal stream and proves that the
lookup exits without consulting or mutating a Context.

## Interactive terminal contract

In an interactive terminal, `mem help` presents the inventory as a
prompt-toolkit selector:

- A shared horizontal choice at the top selects `BY KIND` or `A–Z`; `BY KIND`
  is the default. `VIEW`, both compact bracketed choices, and the Left/Right
  hint occupy one line instead of reserving three rows for choice cards. The
  selected choice retains the shared light-blue selection surface and a visible
  `✓`, while the keyboard target also receives the shared blue focus treatment.
  Left and Right
  change the projection through the common `HorizontalChoiceState` only while
  VIEW has focus. Up from the first command reaches VIEW, and Down returns to
  the command list. In `BY KIND`, Tab advances through each category box in
  screen order before reaching VIEW; Shift-Tab traverses the reverse path.
  Leaving VIEW completes that cycle at the first or last category instead of
  returning to the category beside it and creating a two-stop loop. Each
  category retains its last command cursor while Forms close at a category
  boundary. `A–Z` has one list box, so its Tab path remains VIEW/list. Cross-
  control transitions use the common `SurfaceFocusController`; Help owns only
  its category boundaries plus accelerated internal command/Form movement and
  activation semantics. A view change retains the selected command by name but
  closes its Forms because their row offsets belong to the old projection.
- The two inline choice boxes sit inside one `INVENTORY VIEW` frame, matching the
  common endpoint setup hierarchy where Meld's mode boxes sit inside
  `OPERATION SHAPE`. When VIEW owns keyboard focus, the shared focused-frame
  treatment turns that enclosing border blue and heavy; when focus returns to
  the command list, only the retained choice surface and `✓` remain active.
- `BY KIND` assigns each command one primary discovery category and renders
  each category as one titled box containing all of its command records.
  Category names and their complete execution-basis descriptions are bold so
  each box establishes a visible semantic boundary before its operation rows;
  the surrounding border remains ordinary chrome when the box is not focused.
  Before those categories, one neutral information box contains `CORE
  CONCEPTS`, `COMMON LOCATORS`, and `COMMON KEYS`. It explains Memory, Context,
  Profile, Operation, Grant, Session, and Checkpoint, then makes the shared
  object-location and navigation grammars discoverable. Memory, Context, and
  Profile are defined relationally: Profiles isolate Context stores; Memories
  are independently selectable records stored inside a Context; and Contexts
  contain Memories while `/` expresses child hierarchy.
  The primer explains that operations which support descendant scope may treat
  one Context and its descendants as a subtree, without implying that every
  operation expands descendants automatically.
  Operation is included because the browser's central abstraction is a
  reusable action over selected Memories or Contexts, not merely a shell
  command. It belongs
  to the scrolling inventory rather than the fixed header, so it moves out of
  view as the person browses and does not permanently reduce command space.
  `A–Z` omits this primer entirely and begins with its lexical command box.
  Grant prose describes selectively given or received permission without
  implying ownership, and Checkpoint prose identifies both its per-operation
  creation and per-affected-Context recording boundary. `COMMON LOCATORS`
  distinguishes canonical global bare Context names from `.`, `..`, `./...`,
  and `../...` relative forms, all resolved against one command-start current
  snapshot. It separately explains bare direct-Memory UID discovery and the
  `CONTEXT:UID` owner separator, where UID may be a full identifier or accepted
  prefix, including a relative owner example. This is a
  discovery contract, not a promise that every operation accepts a direct-
  Memory locator; the row explicitly limits that syntax to supporting
  operations. Bare UID ambiguity stops rather than selecting a current or
  first owner, and the operation reports qualified candidates.

  `COMMON KEYS` mirrors the bindings of the Help browser itself: arrows move,
  choose, expand, and collapse; holding vertical arrows accelerates; PageUp and
  PageDown jump ten rows; Home and End reach the first Help row and final
  command; Tab traverses Language, View, and operation groups; Enter opens or
  selects Forms; H opens full command help or hides an Explore overlay; and
  Escape, Q, or Ctrl-C closes the browser. Backspace is deliberately omitted
  because this Help browser does not bind it. Operation-specific footers remain
  authoritative for focus-sensitive wording and modes outside this browser.
  The `MEMORY` type label uses the shared bold light-lavender Memory token,
  making the primer a compact legend for Memory-object text elsewhere in the
  TUI.
  Session copy states its resumable-workflow purpose positively, then points to
  Apply results and checkpoint history as the separate evidence of Context
  mutation. This preserves the lifecycle boundary without framing the Session
  definition as a negation.
  Only that label is tinted: its definition and the other concepts remain
  neutral explanatory prose, while focus may temporarily replace the tint with
  the shared blue treatment.
  Each Core Concept row participates in the same vertical focus path before
  the first command: Up from that command reaches Checkpoint, continued Up
  visits Session through Memory, and only Up from Memory reaches VIEW. Down
  traverses the reverse path. A focused concept supplies a cursor anchor and
  the common blue row/frame treatment so scrolling can keep it visible, but
  Enter, Left, Right, and full-command Help deliberately perform no action.
  Common Locators and Common Keys remain reference prose rather than additional
  focus stops.
  A neutral `OPERATIONS` heading separates this primer from the category boxes
  in both discovery views. The heading makes the list's object explicit without
  adding another nested frame or focus stop.
  Inside a category it preserves an intentional workflow order: orient and
  inspect first, then navigate or create, then perform semantic work, with
  destructive or broad cleanup actions last. Primary commands and any
  separately presented compatibility commands remain adjacent. This order
  comes from `HELP_CATEGORY_GROUPS`; the renderer must not alphabetize it
  again. `A–Z` alone provides lexical lookup.
  Categories follow user intent rather than resource type alone. Browse and
  creation come first; search, deterministic changes, semantic transformations,
  checking/review, the distinct Ground workbench, history, Profiles, access,
  and system/study utilities follow. This keeps within-Context and
  Context-to-Context operations together when they answer the same user goal,
  while each operation's expanded `FLOW`, `EXECUTION`, and `RANGE` remain the
  authoritative scope contract.
  Every BY KIND box includes one short intent description. Pure deterministic
  groups say `NO LLM`; semantic transformations and Ground say `LLM-BASED`;
  route-dependent groups say `MIXED`. System and Study tools omit an execution
  label because configuration and research utilities do not form one useful
  inference class. `DETERMINISTIC CONTENT CHANGES` uses that technical name
  deliberately and explains it as explicit inputs and reviewed choices applied
  through deterministic program logic. `replace` is reserved in a separate
  planned-category registry while its reviewed command is built. Planned names
  cannot enter `HELP_CATEGORY_GROUPS`, whose stale-entry check deliberately
  prevents Help from rendering or accepting a command that does not exist.
  Expanded details may additionally render a canonical structured comparison
  when valid input can be mistaken for object lookup or adjacent operations are
  otherwise easy to confuse. The first such comparison, `add`'s `COPY OR
  LINK`, makes its literal-content boundary explicit and distinguishes
  independent work, immutable Memory or Context References, and live Memory
  or Context Embeds. The Help
  catalog owns that decision meaning so Python, agent, MCP, and terminal callers
  reach the same conclusion; the terminal adapter owns only layout and CLI
  forms. Terminal alternatives use literal `-` markers so rendering does not
  depend on Markdown bullet projection.
  Expanded prose follows the same catalog-owned rule, but remains typed rather
  than entering a generic note bag. Every detail has an operation-local ID and
  a discovery role. Structured `COMPARISON` details also carry bounded route,
  behavior, or verdict options when a flat paragraph would hide a meaningful
  choice. `LIMITATION` records explain an incomplete
  implementation boundary and `ACCESS_BOUNDARY` records explain an authority
  distinction. `SEMANTIC_BOUNDARY` records one concise distinction between
  adjacent semantic operations; Update and Meld share the same revision-oriented
  versus merge-oriented note so neither Help route implies that edit capability
  separates them. The terminal shows their title and body only after expansion;
  Python and agent-facing discovery can address the same detail by its stable
  operation-local ID. A `TOOL_SELECTION` detail exposes one bounded summary
  during MCP discovery; an `ON_DEMAND` detail remains indexed without copying
  its body into every execution tool. Import's current MemCommit-to-MemCommit
  scope and Query's QUERY-without-READ behavior are the first two prose details.
  The same typed-detail path now records Merge's structural cases, ordinary
  Atomize versus `--evaluate`, Distill versus Atomize, Translate materialization
  routes, Impact invocation, Fit verdict examples, and Fit versus Conformance.
  Distill and Conformance expose their adjacent-operation distinction during
  tool selection; syntax and worked verdict examples remain on demand.
  An exact alternate spelling that adds no operation may instead be folded into
  its canonical label, as in `list (ls)` and `delete (remove)`, while remaining
  directly executable. `remove` is therefore not a second deletion operation:
  both spellings reach the same callback and the canonical Delete contract.
  `find-duplicates` and `find-redundancies` remain separate direct, one-Context read-only
  operations: the former reports provider-free exact DUP groups, while the
  latter reports complete exact-plus-semantic DUN evidence. Singular finder
  spellings are accepted parser aliases but remain folded into those canonical
  plural operations. Hyphen-omitted command spellings are likewise executable
  without adding Help rows; underscore-separated spellings remain invalid.
  `A–Z` has no semantic categories, so its complete visible-operation
  projection occupies one `A–Z` box.
  Because that projection owns only one box, the box fills any spare list
  viewport rows with bordered blank lines and places its closing border directly
  above the pinned footer separator. The blank space therefore remains visibly
  part of the complete A–Z inventory instead of resembling additional unboxed
  content. `BY KIND` keeps content-sized boxes and spacing between categories.
- Each command record uses the same vertical semantic structure at every
  terminal width without adding a fixed third row. The first row pairs the
  command with its unlabelled operation summary; the second begins with the
  compact, neutral `WHEN ·` cue and its use case. Every operation owns a
  compact `┬ / │ / └` junction immediately after its displayed label:
  `mem operation ─┬ Summary` and an aligned `└ WHEN · Use case`. The
  resulting ragged Description edge deliberately keeps visual emphasis on the
  left-to-right command list instead of forming one dominant category-wide
  prose block. This binds both learning blocks without a full-width background
  band, blank row, or per-command frame. Description
  continuations retain the vertical guide; When continuations align beneath
  their value after the closing branch. Wide terminals retain
  the same reading order rather than switching to two equal columns. The
  command label may use both physical rows: aliases, annotations, and maturity
  tags occupy its second row, while a long hyphenated command may split after a
  visible hyphen. A four-cell hanging indent keeps that continuation subordinate
  without pushing it past the complete `mem ` prefix. The first row still owns
  the junction; the second label row shares the aligned vertical branch with
  wrapped Description text. This is a presentation-only projection; the canonical
  command spelling, Form, and prefilled command remain unchanged. The box
  containing the focused command uses the
  common blue heavy border, while only the exact focused command or Form gets
  the blue selection surface. Expansion keeps Forms immediately beneath their
  command without introducing a nested command box. The next command begins
  on the line immediately following the prior record, without an empty spacer
  row. Long descriptions and Forms wrap within the current terminal width so
  semantic qualifiers do not vanish beyond the right edge. Every category box
  uses the complete Help viewport up to its one-column scrollbar; it has no
  fixed maximum width that leaves a wide terminal half-empty. Unfocused box
  chrome remains neutral.
- Up and Down move one command at a time or move among one expanded command's
  forms. Holding one direction reuses the shared `NavigationAccelerator`: it
  waits for the terminal's initial key-repeat delay, then increases movement to
  two and five times the terminal repeat cadence, as in the Context/Memory
  selector. Every intermediate command or Form remains a separately visited
  row. Deliberate rapid taps remain one row each, and every non-arrow navigation
  action resets the acceleration streak.
- Page Up, Page Down, Home, and End move through the longer list.
- While the command list is focused, Right expands one command in place and
  immediately moves the focus bar to its
  first `FORM`, matching the newly visible content below the command row. Up
  and Down then inspect the alternative invocations. Left returns from a Form
  to its command row and a second Left collapses the command.
- Enter on a command row expands its Forms and focuses the first Form without
  leaving the browser. Enter on a focused Form then yields that Form's editable
  command template without the parenthesized explanation. This two-stage
  interaction consumes both confirmation key presses inside the TUI, so a
  habitual second Enter cannot reach zsh and execute an unedited placeholder
  such as `[context]`. `H` separately opens the registered command's complete
  syntax help.
- `q`, Escape, and Ctrl-C cancel without selecting or invoking anything.

The hidden prompt-toolkit cursor anchor follows the complete focused command
record (and the complete focused wrapped Form), rather than preceding its first
line. Cursor visibility is the scroll boundary: placing the anchor before a
two-line record allowed the final `mem eval` summary to remain visible while
its `WHEN` row and category border were clipped below the viewport. Anchoring
after the record keeps the whole semantic unit visible at the bottom without
adding a synthetic blank row or changing the fixed footer height.

The scrollable inventory and its fixed footer are separated by the shared
horizontal-rule primitive configured with a one-column right gutter. Its
visible length ends at the same content boundary as the inventory boxes,
leaving the scrollbar's final column blank. This avoids a one-cell overhang
that otherwise makes the bottom rule look wider than the `A–Z` box. Spare
terminal height remains part of the list viewport, while the rule and key guide
stay pinned at the bottom.

The selected command's callback is deliberately never invoked. Some commands
can change local state with no additional arguments, while other commands
require operands or provider work. No Enter in the browser invokes the selected
command callback; selection only returns editable shell text. Execution remains
a later, separate Enter after the person has reviewed and edited that text.

The same inventory also has a stricter `EXPLORE` presentation used by the
shared interactive command-wait screen, where a previously completed review
report is the default foreground while submitted guidance is incorporated.
In that mode Enter and Right keep descriptions and audited Forms inside Help;
they never return a shell template. `H` or `h` opens Help from the report,
confirmed-input copy, or read-only Context browser and hides it back to the
same surface; `Q`, `q`, or Escape also returns. A completed background turn
appears as `RESULT READY · H / Q RETURN` without closing Help. Initial semantic
analysis has no completed review and stays on the one-line progress contract,
so it does not open this Help-capable full-screen surface. The
inventory data and renderer remain shared; only the caller-owned visibility
and exit policy differs. Ordinary `mem help` retains `H` for full command help.
The sibling wait destinations are `C/c` for a browse-only switch-shaped
Context tree, `I/i` for supplied confirmed inputs, and `R/r` for a supplied
report. Repeating the active destination key returns to its immediate origin,
matching `H/h` open/hide without reviving the former unnamed C-only toggle.
`m/M` may reveal Memory previews inside the Context tree, but that surface has
no switch receipt or current-Context mutation path.
See
[`command-wait-destination-browser-design-rationale.md`](command-wait-destination-browser-design-rationale.md)
for the destination and browse-only boundary, and
[`interactive-command-wait-design-rationale.md`](interactive-command-wait-design-rationale.md)
for background execution consistency.

Long-lived terminal sessions now reuse that same `EXPLORE` renderer through
the operation-neutral Session Help controller. On a read-only navigation
surface, `H` or `h` opens `mem help · session guide`; the same key hides it and
restores the exact parent focus and buffers. Writable Questions, Search text,
Messages, Responses, comments, direct edits, and exact names retain both
letters as ordinary input. Query, Find, Compare, Result, Resolution, and Ground
share this lifecycle without sharing semantic or persisted session state. See
[`session-help-design-rationale.md`](session-help-design-rationale.md).

The child `mem help` process does not modify its parent shell's edit buffer.
After a Form is selected, Help instead opens the shared exact-command editor
with the operation prefix fixed. Enter validates the edited arguments, closes
Help, and invokes that exact argv as a separate child process without shell
interpretation. The retired parent-shell prefill design and its replacement
boundary are recorded in
[`mem-zsh-prefill-design-rationale.md`](mem-zsh-prefill-design-rationale.md).

When stdin or stdout is not a TTY, `mem help` retains the stable plain-text
inventory. This keeps pipes, captured study records, and automated tests
deterministic instead of emitting a terminal-control interface.

## Compact annotations

Ordinary commands carry no implementation label. Repeating `implemented` on
nearly every row adds noise without helping a person choose a command. A
parenthesized status annotation is reserved for exceptional compatibility
state. `config (legacy)` remains a low-level stored-setting interface, while
`eval (legacy)` remains the fixed research campaign harness pending a general
evaluation interface. Both remain callable. A separate exact-spelling annotation groups an executable hidden
spelling with its canonical operation, as in `list (ls)` and
`delete (remove)`; it does not classify a conditional dispatcher such as
`checkout` as an alias. Retired commands such as `integrate` are omitted
instead of occupying an inventory row that suggests they can still be selected.
Ordinary TUI entry is described inside expanded Forms instead of repeating a
badge across the inventory.

One implementation-scope exception may use a compact bracketed maturity tag.
`import [PARTIAL]` keeps Import's ordinary Summary and `USE WHEN` readable in
the collapsed inventory, while its expanded `CURRENT LIMITATION` detail states
exactly which transfers exist and which broader import/export routes do not.
This tag is Help-facing product maturity, not an operation-route judgment: it
must not be interpreted as, or copied into, the separate `CLOSED`, `MIXED`,
`LEGACY`, `N/A`, and `UNREVIEWED` evidence ledger.

## Invocation forms

Expansion lists complete meaningful entry forms rather than presenting one
generic Click usage line. Interactive forms name the surface entered instead
of enumerating its internal choices. A saved-or-new operation picker is an
`interactive <Operation> session launcher`; a bound operation opens an
`interactive <Operation> session`; and non-session surfaces are named as a
selector, browser, viewer, or setup according to their actual role. This keeps
the compact contract stable when a launcher's saved and New rows evolve, while
avoiding the false implication that every interactive picker is durable
session state.

For example, Meld distinguishes its bare new-operation setup from its explicit
`--sessions` launcher, symmetric peers, a require-new symmetric Result, canonical
`INCOMING --into BASELINE`, and the current-Baseline `--from` convenience form.
Each form includes a short parenthesized semantic label when the operands alone
would not explain the route. Bracketed lowercase values such as `[context1]`,
`[context2]`, and `[result_context]` are editable placeholders. They identify
both the kind and number of values to replace instead of exposing
implementation-relative roles such as LEFT and RIGHT; the brackets are not
literal operands or a claim that the corresponding CLI parameter is optional.
Memory-facing forms name the value's semantic role rather than collapsing
different strings into `[memory]`: Add uses `[memory_content]` for literal new
content, while Edit, Reference, Embed, Trace, and other object routes use
`[memory_selector]` for an existing Memory UID or unambiguous prefix. Reference
separately labels `--from [source_context]`; that option never accepts the
Memory selector. Edit labels `--input [batch_file]` because it consumes
UID-tab-content records rather than inline replacement content.
Free-text placeholders that commonly contain whitespace retain double quotes
in both the displayed Form and the selected shell template. Structured names,
UIDs, flags, and paths remain unquoted so their token boundaries stay visible.

Every currently visible top-level command has an explicitly audited, bounded
form list. This is necessary even for apparently simple callbacks: Click
cannot reveal that `profile NAME` is routed through a group alias or that bare
`lock` changes the current Context. A conservative registered-operand fallback remains for a
new command before its inventory is updated, but the test contract requires
all shipped commands to replace that fallback with reviewed forms.

The form lists follow one bare-route rule: if a callback has a meaningful
no-argument behavior, its exact `mem <name>` spelling appears as a Form.
This prevents a current-target route, generated default, or interactive picker
from disappearing merely because the same callback also accepts operands or
subcommands. Parser-valid spellings whose callback deliberately returns a
usage error, such as bare `mem impact`, are not advertised as meaningful Forms.
Bare `mem query` now appears because a terminal opens its interactive Question
and Source workbench; outside a terminal it still requires an explicit
selector. Bare Reference exposes an explicit Context/Memory snapshot-unit
setup and Edit exposes its direct-Memory setup, while their non-TTY routes
retain explicit operands. Group help alone is
also not treated as an operation, while
groups with real bare callbacks (`lock`, `unlock`, and `profile`) expose them.

For example, `mem update` exposes its bare Source/Target setup and separate
`mem update --sessions` saved-work launcher before its directional endpoint forms,
while `mem impact` omits bare invocation because it requires a directional or
named operation route. Its expanded Forms enumerate `impact atomize`, the
process-local `impact forget`, `impact distill`, and `impact resolve`
previews, the three directional Update planners, and the saved-session
inspections `impact meld`, `impact sever`, and `impact update`; the latter may
also name an exact artifact with `--session UID`. The process-local Form labels
state that no Source is changed and no Result is created. The saved-session
Form labels name the optional `APPLY?` handoff so the inventory does not
misdescribe Impact as a dead-end viewer: the handoff opens the owning
operation's separate Apply flow and does not itself mutate anything. This is
intentionally more explicit than the optional positional operand shown by
generic parser usage, because the operation names select materially different
artifacts and provider boundaries. A message-less `mem checkpoint` and the
default-English `mem translate` route are likewise shown because both are
callable behaviors, not syntax errors. `search` exposes its bare interactive
search-and-scope route and describes the default descendant-and-embed frame.
Its Forms deliberately advertise no implicit History route: time-oriented
words remain current-content query text, while retained-history semantics are
entered explicitly through `mem log QUERY`. Resource
imports and write-protection
groups enumerate their distinct public grammars rather than collapsing them
into ambiguous positional placeholders.

`embed` likewise exposes its bare Child/Into/insertion-gap form and keeps the
explicit append, `--before`, and `--after` command shapes separately visible.
The item anchor is part of the durable direct-item order contract rather than a
secondary presentation flag.

The list intentionally omits secondary action flags such as comments,
responses, snapshots, and acceptance controls; `H` retains the complete
registered syntax reference. A selected Form preserves its bracketed
placeholders in the Help-owned exact command editor; execution remains a
separate Enter after review.

A deliberately bounded command needs no status annotation when its
advertised contract is available. For example, `merge` intentionally performs
structural UID union without semantic reconciliation, and `diff` intentionally
renders the active update rather than comparing arbitrary Contexts. The
inventory describes the contract people can actually invoke, not a broader
operation suggested by the command's name or a production-readiness claim.
Individual commands may still have documented permission, provider,
concurrency, or remote-persistence boundaries.

An implementation can keep two executable spellings without presenting them
as two operations. Help shows the canonical `list` entry once as `list (ls)`;
the hidden `ls` registration remains an exact compact spelling with the same
callback and grammar. This keeps discovery beginner-readable while preserving
the shell-familiar form in scripts and direct use.

`checkout` is not described as an alias because its public grammar selects
between two distinct operations. It is a Git-style compatibility command:
without `-b` it routes to Switch, while `-b` routes to Branch. Bare `checkout`
therefore enters the Switch picker, and bare `checkout -b` enters Branch's
Source-and-name setup. The inventory states those behaviors directly instead
of implying that the complete `checkout` command is interchangeable with
either underlying command.

## Consistency boundary

The small interface-neutral `OperationHelp` catalog owns each public
operation's canonical summary plus four deliberately bounded semantic fields:
flow, execution kind, effect, and an optional range. The root Typer
registration reads its summary from that catalog, and command inventory
construction fails closed if either coverage or the registered summary
diverges. Callback docstrings remain implementation documentation; they are
not copied into user-facing Help because many callbacks are compatibility or
adapter entry points rather than the complete operation contract.

The catalog is intentionally not a second implementation. CLI flag spelling,
parameter types, and defaults remain owned by Typer. Audited invocation Forms
remain CLI projections because interactive entry routes and semantic route
labels cannot be inferred from parser syntax alone. Current Profile authority,
Grant resolution, cache decisions, and provider receipts remain runtime
results. Detailed algorithms and design tradeoffs remain in focused rationale
notes. These boundaries keep routine CLI changes from requiring a parallel
semantic policy update.

The pure Help composer combines `OperationHelp` with interface-owned material.
The expanded TUI entry projects the common flow, execution, effect, and range
before its exact CLI Forms. Selected full Help renders the same overview and
Forms before Typer's complete syntax reference. Plain non-TTY inventory stays
compact and deterministic. Future Python or agent-tool adapters may project
the same catalog without importing prompt-toolkit or reconstructing CLI
strings.

Compact spelling/status annotations and multi-route invocation forms remain
explicit because equivalent spellings, compatibility state, and semantic entry
routes cannot be inferred safely from Click registration alone.

The renderer fails closed if an annotated or explicitly formed command is no
longer registered. Tests also require every visible command to have an audited
form list, recursively parse every selected template without invoking its
callback, and require a bare Form for every meaningful bare callback. This
catches stale options, wrong nested subcommands, missing required operands,
and hidden picker/current-target routes without running mutations or provider
work. Ordinary new commands need no redundant `implemented` entry, but their
forms must be reviewed before the inventory contract is considered complete.

Only callable visible commands are listed. Proposed but unregistered
operations are omitted rather than shown as commands a participant could try.
Their design state remains in the focused operation rationale documents and
the external function inventory.

## Process-local learning languages

Interactive `mem help` exposes `EN · FR · ZH · KO · MN` in a LANGUAGE control
above VIEW. The selection is process-local, starts at English on every launch,
and changes no Profile, Context, Memory, session, provider input, or study
fixture. In study-owned session Help, a language change is recorded only as a
content-free `HELP LANGUAGE <code>` TUI action so language exposure can be
accounted for without altering the task data.

The localized learning layer covers Core Concept definitions, common-locator
and common-key guidance, category descriptions, and every operation's collapsed
`DESCRIPTION` and `USE WHEN` prose. Command names, flags, Forms, and the
  canonical nouns `Memory`, `Context`, `Profile`, `Operation`, `Grant`,
  `Session`, and `Checkpoint` stay English so translated guidance continues to
  name the exact objects and commands the participant must operate. Expanded
Flow/Execution/Effect/Range values and typed route details also remain the
canonical English contract in this initial rollout; translating those safety
and invocation boundaries requires a separate reviewed parity pass rather than
an unchecked fallback.

All four non-English operation catalogs are checked in under
`application/operations/operation_catalog/translations` and must cover exactly
the same 65 visible operation names. Help-specific interface guidance remains
with the console Help adapter and has its own cross-language key coverage.
Runtime provider translation is deliberately not used: two participants
choosing the same language must see the same copy.
`ZH` and `KO` use language rather than country codes; `MN` currently denotes
Mongolian Cyrillic. The renderer wraps and pads translated prose by terminal
cells rather than Python character count, because Chinese and Korean glyphs
occupy two terminal columns. The screenshot renderer uses CJK-capable fallback
fonts while preserving the actual color PTY stream and cell placement.
The evidence renderer paints all ANSI cell backgrounds before drawing glyphs:
a CJK glyph lives in one leading terminal cell but spans two, so painting a
styled following cell afterward could erase half of that glyph even though the
live terminal and raw PTY text are correct.

## Relationship to `mem --help`

`mem --help` remains Typer's syntax-oriented reference, including global
options. `mem help` is the compact implementation inventory and interactive
syntax browser. Per-command syntax continues to use:

```text
mem <command> --help
```

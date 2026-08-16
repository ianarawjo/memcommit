# `mem help` design rationale

## Intent

The default Typer help output proves that a command is registered, but its
syntax-first layout is harder to scan as a complete command inventory. That
distinction matters while building the study prototype and when preparing its
printed cheat sheet.

`mem help` therefore renders one concise inventory line per visible registered
command. The interactive browser offers two projections of the same audited
metadata: `BY KIND` for intent-first discovery and `A–Z` for exact-name lookup.
The stable non-TTY inventory remains case-insensitive A–Z for scripts and
captured study output:

```text
name [(exact spelling)] [(status)] - short description
```

It reports capabilities; it does not recommend a command sequence or perform
work for the participant. Source registration order remains free to group
related implementation code; neither Help projection depends on it.

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
  Before those categories, one neutral `CORE CONCEPTS` and
  `COMMON KEYS` information box explains Memory, Context, Profile,
  Grant, Session, and Checkpoint plus the shared navigation grammar. It belongs
  to the scrolling inventory rather than the fixed header, so it moves out of
  view as the person browses and does not permanently reduce command space.
  `A–Z` omits this primer entirely and begins with its lexical command box.
  Grant prose describes selectively given or received permission without
  implying ownership, and Checkpoint prose identifies both its per-operation
  creation and per-affected-Context recording boundary. The Backspace hint
  concisely states the writable-field exception without repeating a read-only
  qualifier in the heading or navigation action. Operation-specific footers
  remain authoritative for keys that are not common enough to appear in this
  primer.
  The `MEMORY` type label uses the shared light-lavender Memory token, making
  the primer a compact legend for Memory-object text elsewhere in the TUI.
  Only that label is tinted: its definition and the other concepts remain
  neutral explanatory prose, while focus may temporarily replace the tint with
  the shared blue treatment.
  Each Core Concept row participates in the same vertical focus path before
  the first command: Up from that command reaches Checkpoint, continued Up
  visits Session through Memory, and only Up from Memory reaches VIEW. Down
  traverses the reverse path. A focused concept supplies a cursor anchor and
  the common blue row/frame treatment so scrolling can keep it visible, but
  Enter, Left, Right, and full-command Help deliberately perform no action.
  Common Keys remains reference prose rather than five additional focus stops.
  Inside a category it preserves an intentional workflow order: orient and
  inspect first, then navigate or create, then perform semantic work, with
  destructive or broad cleanup actions last. Primary commands and any
  separately presented compatibility commands remain adjacent. This order
  comes from `HELP_CATEGORY_GROUPS`; the renderer must not alphabetize it
  again. `A–Z` alone provides lexical lookup.
  `MECHANICAL MEMORY OPERATIONS` groups provider-free actions whose result is
  determined by explicit identities, text boundaries, replacement values, or
  reviewed deterministic choices. `SEMANTIC MEMORY OPERATIONS` groups
  meaning-based analysis, transformation, and review workflows. The latter
  label does not promise a provider call for every form: an exact cache hit or
  saved-artifact replay may remain local, and each operation's `EXECUTION` row
  is authoritative. The two category boxes expose that distinction directly:
  Mechanical says `NO LLM`, while Semantic says `LLM-BASED` and explicitly
  allows either a provider call or reuse of exact cached or saved analysis.
  This text classifies the source of meaning rather than promising a fresh
  call. Forget belongs to the semantic group because it interprets one
  natural-language criterion over a complete Memory frame; Merge and Dedup
  belong to the mechanical group because their application choices are exact
  and provider-free.
  An exact alternate spelling that adds no operation may instead be folded into
  its canonical label, as in `list (ls)` and `delete (remove)`, while remaining
  directly executable. `remove` is therefore not a second deletion operation:
  both spellings reach the same callback and the canonical Delete contract.
  `A–Z` has no semantic categories, so its complete visible-operation
  projection occupies one `A–Z` box.
  Because that projection owns only one box, the box fills any spare list
  viewport rows with bordered blank lines and places its closing border directly
  above the pinned footer separator. The blank space therefore remains visibly
  part of the complete A–Z inventory instead of resembling additional unboxed
  content. `BY KIND` keeps content-sized boxes and spacing between categories.
- Each command record keeps its name and description on one aligned line
  inside the owning category box. A description wraps only when the terminal
  width requires it, with continuation text aligned to its original start
  column. The box containing the focused command uses the
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
shared interactive command-wait screen, where an operation-owned report or
report skeleton is the default foreground.
In that mode Enter and Right keep descriptions and audited Forms inside Help;
they never return a shell template. `H` or `h` opens Help from the report,
confirmed-input copy, or read-only Context browser and hides it back to the
same surface; `Q`, `q`, or Escape also returns. A completed background turn
appears as `RESULT READY · H / Q RETURN` without closing Help. The
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

The child `mem help` process cannot itself prefill its parent shell's next
editable command line. The opt-in output of `mem shell-init zsh` now supplies
a parent-shell wrapper for zsh: its private selection mode keeps the TUI on
the terminal, returns one validated command name to the wrapper, and uses
zsh's `print -z` to prefill without executing. Bash Readline and Fish still
need their own integrations. Unsafe terminal input injection is not used.
See [`mem-zsh-prefill-design-rationale.md`](mem-zsh-prefill-design-rationale.md)
for that shell-owned boundary.

When stdin or stdout is not a TTY, `mem help` retains the stable plain-text
inventory. This keeps pipes, captured study records, and automated tests
deterministic instead of emitting a terminal-control interface.

## Compact annotations

Ordinary commands carry no implementation label. Repeating `implemented` on
nearly every row adds noise without helping a person choose a command. A
parenthesized status annotation is reserved for exceptional compatibility
state: `config (legacy)` remains callable but sits outside the current
workflow. A separate exact-spelling annotation groups an executable hidden
spelling with its canonical operation, as in `list (ls)` and
`delete (remove)`; it does not classify a conditional dispatcher such as
`checkout` as an alias. Retired commands such as `integrate` are omitted
instead of occupying an inventory row that suggests they can still be selected.
Ordinary TUI entry is described inside expanded Forms instead of repeating a
badge across the inventory.

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

For example, Meld distinguishes its bare interactive session launcher,
symmetric peers, a require-new symmetric Result, canonical
`INCOMING --into BASELINE`, and the current-Baseline `--from` convenience form.
Each form includes a short parenthesized semantic label when the operands alone
would not explain the route. Bracketed lowercase values such as `[context1]`,
`[context2]`, and `[result_context]` are editable placeholders. They identify
both the kind and number of values to replace instead of exposing
implementation-relative roles such as LEFT and RIGHT; the brackets are not
literal operands or a claim that the corresponding CLI parameter is optional.
Memory-facing commands similarly use `[memory]` instead of generic parser
names such as INFO, SELECTOR, or UID when Memory is the user-facing object.
Free-text placeholders that commonly contain whitespace retain double quotes
in both the displayed Form and the selected shell template. Structured names,
UIDs, flags, and paths remain unquoted so their token boundaries stay visible.

Every currently visible top-level command has an explicitly audited, bounded
form list. This is necessary even for apparently simple callbacks: Click
cannot reveal that a temporal `find` is selected from the wording of its query,
that `profile NAME` is routed through a group alias, or that bare `lock` changes
the current Context. A conservative registered-operand fallback remains for a
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
selector. Group help alone is also not treated as an operation, while
groups with real bare callbacks (`lock`, `unlock`, and `profile`) expose them.

For example, `mem update` exposes its interactive Update session launcher
before its three directional endpoint forms,
while `mem impact` omits bare invocation because it requires a directional or
named operation route. Its expanded Forms enumerate `impact atomize`, the
three directional Update planners, and the saved-session inspections
`impact meld`, `impact sever`, and `impact update`; the latter may also name an
exact artifact with `--session UID`. Those saved-session Form labels also name
the optional `APPLY?` handoff so the inventory does not misdescribe Impact as
a dead-end viewer: the handoff opens the owning operation's separate Apply
flow and does not itself mutate anything. This is intentionally more explicit
than the optional positional operand shown by generic parser usage, because
the operation names select materially different saved artifacts and provider
boundaries. A message-less `mem checkpoint` and the default-English
`mem translate` route are likewise shown because both are callable behaviors,
not syntax errors. `find` exposes its bare interactive search-and-scope route,
describes the default descendant-and-embed frame, and describes retained-history
selection as an explicitly temporal query instead of inventing a `--history`
option that the parser does not implement. Resource imports and write-protection
groups enumerate their distinct public grammars rather than collapsing them
into ambiguous positional placeholders.

`embed` likewise exposes its bare Child/Into/insertion-gap form and keeps the
explicit append, `--before`, and `--after` command shapes separately visible.
The item anchor is part of the durable direct-item order contract rather than a
secondary presentation flag.

The list intentionally omits secondary action flags such as comments,
responses, snapshots, and acceptance controls; `H` retains the complete
registered syntax reference. A selected Form preserves its bracketed
placeholders when prefilled as editable shell text by the opt-in zsh
integration; selection never executes it.

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

## Relationship to `mem --help`

`mem --help` remains Typer's syntax-oriented reference, including global
options. `mem help` is the compact implementation inventory and interactive
syntax browser. Per-command syntax continues to use:

```text
mem <command> --help
```

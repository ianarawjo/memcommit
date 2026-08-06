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
name [(exception)] - short description
```

It reports capabilities; it does not recommend a command sequence or perform
work for the participant. Source registration order remains free to group
related implementation code; neither Help projection depends on it.

## Interactive terminal contract

In an interactive terminal, `mem help` presents the inventory as a
prompt-toolkit selector:

- A shared horizontal choice at the top selects `BY KIND` or `A–Z`; `BY KIND`
  is the default. Left and Right change the projection only while that row has
  focus. Up from the first command reaches VIEW, Down returns to the command
  list, and Tab/Shift-Tab traverse the same two visible surfaces. A view change
  retains the selected command by name but closes its Forms because their row
  offsets belong to the old projection.
- `BY KIND` assigns each command one primary discovery category and renders
  nonselectable category headings. Aliases remain separate commands in the
  same category so the inventory still describes every registered spelling.
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

The selected command's callback is deliberately never invoked. Some commands
can change local state with no additional arguments, while other commands
require operands or provider work. No Enter in the browser invokes the selected
command callback; selection only returns editable shell text. Execution remains
a later, separate Enter after the person has reviewed and edited that text.

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

## Exceptional annotations

Ordinary commands carry no implementation label. Repeating `implemented` on
nearly every row adds noise without helping a person choose a command. A
parenthesized annotation is reserved for exceptional compatibility state:
`integrate (legacy)` and `config (legacy)` remain callable but sit outside the
current workflow. Ordinary TUI entry is described inside the expanded Forms
instead of repeating a badge across the inventory.

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
usage error, such as bare `mem impact` or `mem query`, are not advertised as
meaningful Forms. Group help alone is also not treated as an operation, while
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
not syntax errors. `find` describes retained-history selection as an explicitly
temporal query instead of inventing a `--history` option that the parser does
not implement. Resource imports and write-protection groups enumerate their
distinct public grammars rather than collapsing them into ambiguous positional
placeholders.

The list intentionally omits secondary action flags such as comments,
responses, snapshots, and acceptance controls; `H` retains the complete
registered syntax reference. A selected Form preserves its bracketed
placeholders when prefilled as editable shell text by the opt-in zsh
integration; selection never executes it.

A deliberately bounded command needs no exception annotation when its
advertised contract is available. For example, `merge` intentionally performs
structural UID union without semantic reconciliation, and `diff` intentionally
renders the active update rather than comparing arbitrary Contexts. The
inventory describes the contract people can actually invoke, not a broader
operation suggested by the command's name or a production-readiness claim.
Individual commands may still have documented permission, provider,
concurrency, or remote-persistence boundaries.

An implementation can expose two related public spellings through one
internal callback. `mem list` and `mem ls` deliberately have the same
description: participants may learn and use either spelling. A compatibility
alias such as `checkout` identifies its explicit `switch` and `branch`
operations directly in its description instead of adding another status
column. It does not claim the bare interactive `switch` picker because
`checkout` requires a name.

## Consistency boundary

Descriptions are read from the same Click/Typer command registrations used by
`mem --help`; the inventory does not maintain a second description catalog.
Exceptional annotations and multi-route invocation forms are explicit because
compatibility status and semantic entry routes cannot be inferred safely from
Click registration alone.

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

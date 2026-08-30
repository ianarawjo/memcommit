# Interactive Query workbench design rationale

Last verified: 2026-08-26.

## Problem

The previous workbench permanently displayed a large Source tree, then added
Scope, optional Session Name, Saved Transcripts, Answer, and To Do frames. The
screen gave a one-shot read operation the visual and persistence weight of a
resumable review workflow. It also diverged from the compact Source selector
already used by Find and other setup screens.

Query still has two distinct Source boundaries. Ordinary Query reads a frozen
set of visible readable Contexts. Query Views use public grant routes and must
not open concealed authority content before provider authentication. A clean
surface must preserve that type distinction without keeping either catalog
expanded all the time.

## Decision

Bare `mem query` in a TTY opens one compact, process-local workbench:

1. `SCOPE` contains a Source-type choice and a one-line exact Source field;
2. `[ BROWSE ]` opens the relevant catalog only while the user is choosing;
3. range and embed controls stay adjacent to the Source they affect;
4. `QUESTION` is the initial focus and Enter performs one Query; and
5. `ANSWER` displays the current process-local result and typed References.

There is no Session Name, Saved Transcripts, or To Do frame. Closing the
workbench discards its question draft, selection state, and answer. The only
explicit output action is copying the current typed answer or focused
Reference to the ordinary OS clipboard.

For ordinary Contexts the screen composes `CompactReadableScopeControl`, the
same exact-name plus transient Browse grammar used by Find. Direct name input
is the fast path. Browse temporarily replaces the normal focus topology with
the frozen readable tree; Escape, Backspace, or Tab closes it and returns to
the compact row. The shared control continues to own exact-versus-descendant
range, Profile expansion, checked effective targets, and embed traversal.

Query Views use an operation-specific typed companion with the same visual
grammar. Direct input accepts only a public name from the frozen authorized
catalog. Browse shows typed `GrantedQueryTarget` rows and never substitutes an
ordinary Context locator. Exact View versus federated descendants remains an
independent range choice.

## Execution and focus boundary

Opening the workbench, moving focus, typing a Source name, or browsing does not
connect a provider. Enter in Question constructs either an
`OrdinaryQueryRequest` or `GrantedQueryRequest`, then runs it through the
shared background-turn lifecycle. A blank question in either Source mode is
rejected before provider construction. A positional readable Context or
QUERY-only View can open the same workbench with that typed target selected;
explicit `-d` or `-r` initializes its visible reach control.

Normal vertical order is Source type, exact Source, Browse, range, optional
embed policy, Question, then Answer. While a catalog is open it is the sole
focus Surface. Escape closes that transient layer first, returns to Question
from another root Surface second, and closes from Question. Backspace mirrors
the one-level return only for read-only controls and remains text deletion in
the exact Source and Question fields.

The Answer document retains the neutral body and typed used References as one
linear Up/Down sequence. Lowercase `y` copies the focused typed unit; uppercase
`Y` copies the complete typed answer. Clipboard projection happens before
terminal wrapping and does not persist a memcommit artifact.

## Persistence and authority invariants

- Workbench selection, draft, answer, authorized Source catalog, and focus are
  process-local.
- Query has no durable publication stage and no success action after Answer;
  therefore a To Do frame would be false workflow chrome.
- Ordinary Browse freezes `ReadableContextCatalog`, including effectively
  READ-granted public names with their exact access bindings.
- Query View Browse freezes public grant metadata only. Provider construction
  precedes concealed Source loading, and post-provider revalidation precedes
  answer disclosure.
- The exact checked ordinary target set is executed; no hidden descendant
  expansion re-includes an independently unchecked row.
- CLI flags retain explicit direct and recursive one-shot forms, while the TUI
  owns its visible scope controls.

## Alternatives considered

- **Keep the full tree visible:** rejected because selection metadata dominates
  the question and answer even when the user already knows the Source name.
- **Use one untyped Browse list:** rejected because ordinary readable Contexts
  and query-only Views have different loading and disclosure authority.
- **Keep Saved Transcripts but hide the frame:** rejected because invisible
  persistence still leaves the session permission, replay, storage, and API
  contracts.
- **Keep To Do as a close action:** rejected because closing is terminal
  navigation, not an operation outcome or reviewed materialization step.
- **Call the Typer callback from the TUI:** rejected because stdout/progress
  rendering and positional string inference do not belong inside the
  full-screen state machine.

## Interface ownership

The screen, presentation adapter, model, and Query View scope control live under
`memcommit.adapters.console.commands.query.workbench`. Ordinary compact selection stays
owned by `memcommit.adapters.console.terminal.components.operation_context_scope_editor.readable_scope_editor`. Terminal-independent
requests and execution live in `memcommit.application.operations.query`; no operation
application module imports prompt-toolkit or command code.

## Verification

`tests/test_query_workbench.py` covers no-connect entry, transient ordinary
Browse, typed Query View routing and preselection, blank-question rejection,
one-shot request freezing, absence of Saved Transcripts/To Do, and typed
Reference copy projection.
The ordered real-color 180×52 evidence under
`agent-records/docs/screenshots/query-compact-one-shot-20260822/` records ordinary entry,
Browse, question, provider progress, answer, Reference focus, final no-write
verification, and the separate public-only Query View Browse boundary.

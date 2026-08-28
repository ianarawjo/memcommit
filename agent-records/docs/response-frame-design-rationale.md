# Common Responses frame design rationale

## Motivating problem

Actionable Atomize, Meld, Sever, Forget, Update, and adaptive Review screens
all need the same person-facing controls: an operation-authored question,
zero or more proposed choices, one staged selection, and an optional multiline
response. Keeping those controls as Viewer sections made the evidence report
own writable state and encouraged adapters to repeat saved responses as report
blocks. The result was inconsistent focus granularity and more than one visual
location for the same answer.

## Contract

`memcommit.adapters.console.terminal.components.responses` is the service-wide presentation contract.
It lives under the console interface because its state composes console selection
controls and its renderer owns terminal interaction; this placement does not give
it provider, persistence, mutation, or application authority:

- `ResponseTarget` identifies one current answerable item and supplies labels,
  obligation, state, question, choices, and editability.
- `ResponseDraft` carries only a selected opaque choice UID and free-form text.
- `ResponseFrameState` owns process-local Decision/Response focus, choice
  cursor, and editor state.
- the TUI renderer owns common status, focus, selection, and input affordances.

The contract contains no provider, persistence, mutation, or Apply authority.
Each operation continues to validate and store its own durable response model,
and its controller remains the only layer that may incorporate, materialize,
or apply the reviewed result.

## Topology and focus

The complete report starts in Viewer with no synthetic response frame. When an
answerable item is opened or previewed, the visible order is:

```text
VIEWER → RESPONSES → ITEMS → [SAVE LOCATION] → TO DO
```

Viewer contains evidence, source Memories, reasoning, and proposed outcomes.
Responses contains Decision and Response. Items contains review targets only.
To Do derives the one whole-session next action. Final Review and Apply omits
Responses because it confirms already staged state rather than collecting new
item input.

The live Responses body does not repeat the current item title, obligation, or
open/answered status. Viewer and Items already provide those orientation facts;
Responses reserves its limited height for the question, choices, and free-form
answer. Stable non-interactive snapshots may retain surrounding report context
supplied by their caller.

The question is explanatory chrome rather than a focus stop. Entering
Responses focuses the checked choice, or the first proposed choice when no
value is staged. Up/Down moves directly through every visible choice and then
Response; moving up from Response restores the checked choice when one exists.
Enter on a choice stages or clears its opaque UID, while Enter on Response opens the
multiline field. Enter saves, `Ctrl-J` inserts a newline, and Escape cancels the
edit without silently replacing the durable draft.

Response is a separate inner box below the real operation-supplied choices,
built with the same shared framed multiline primitive used by other terminal
composers. It is not fabricated as a final `Different` selection card. Moving
into or editing that box does not itself clear a checked choice; free-form text
may remain independent guidance or accompany the selected reading according to
the operation adapter's existing contract.

Hover and selection remain distinct. Moving over another choice is temporary;
crossing into Response or leaving the frame restores the choice cursor to the
checked UID when one exists. Returning therefore acts on the durable selection
rather than a stale exploratory row without changing the stored draft.

Decision choices reuse the service-wide flat selection state but project it as
unboxed stacked rows in Responses. The current label line receives the blue
focus fill and bold text; its wrapped description receives the same fill
without bold so explanatory prose does not become another heading. A staged
value carries `✓`, including after keyboard focus moves away. The hidden
viewport anchor follows the complete focused row group. `SelectionOption` and
`FlatSelectionState` continue to own cursor and checked-value mechanics while
the Response adapter retains draft and persistence meaning. See
`agent-records/docs/selection-control-design-rationale.md`.

The nested Response box must remain neutral while a choice row owns focus.
Bind its dynamic chrome before the outer Responses frame and reset inherited
text style at the inner boundary; otherwise the outer focused frame makes both
the choice and Response box appear active simultaneously.

## Operation adapters

Resolution adapters project their existing `ResolutionItem` values through
`response_target_from_item`. Durable Atomize responses, Meld decisions, Sever
and Forget treatments, and Update change comments retain their existing
schemas and execution semantics. Atomize no longer adds a duplicate `SAVED
RESPONSE` Viewer block; the common frame is the single display location.

The legacy `mem review ambiguities` and `mem review atomize` command path now
uses a dedicated projection into the same Resolution workbench. Its
`ReviewSession` JSON remains unchanged. The older snapshot renderer remains for
stable non-interactive output and compatibility; it is not the live command's
interaction grammar.

## Boundaries and alternatives

Ground comments and Find queries reuse lower-level terminal input primitives,
not the response semantic contract: they are conversational or search input,
not answers bound to a reviewed item. Save Location is also independent because
it edits a materialization target rather than a response.

Keeping Response inline in Viewer was rejected because it couples writable
state to evidence navigation and makes the frame order depend on operation-
specific report blocks. A global response store was also rejected: persistence,
provider incorporation, and application authority differ by operation and must
remain behind their existing validation and CAS boundaries.

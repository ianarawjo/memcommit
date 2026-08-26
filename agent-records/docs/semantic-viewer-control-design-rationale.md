# Semantic Viewer control policy

## Motivation

Section-oriented terminal screens previously shared colors and some key
bindings but did not share the boundary of one focus move. Atomize flattened
`UNDERSTOOD`, `CHANGED`, and `UNRESOLVED` into one overview string, while an
actionable Source Memory was split into one stop per terminal-wrapped line.
The first boundary was too broad; the second changed when the terminal width
changed.

The application needs one interaction policy without forcing operations into
one semantic result model. An operation knows which claims, Memories, and
decisions can be reviewed independently. The common Viewer knows how focus,
movement, viewport anchoring, and nested reading must behave.

## Contract

An operation declares stable semantic sections. The shared
`SemanticViewerController` consumes either a `SemanticViewerDocument` or the
same ordered `WorkbenchSection` projection and owns:

- current stable section UID and index clamping;
- Up/Down, paging, Home, and End movement;
- rendering the active document section through the common focus policy; and
- a nested index that can inspect a long block without changing its outer UID.

The controller never parses report prose, chooses an operation action, or
persists state. Resolution, Result, Compare, and Share retain their own typed
artifacts and action validation.

The semantic boundary rules are:

- report title, Context locations, status, metrics, and group headings are
  orientation chrome rather than focus stops;
- one operation-declared report claim is one stop;
- one displayed Memory object is one outer stop, independent of wrapping;
- an operation-authored Viewer Decision may remain one outer stop with nested
  choices, while the independent Responses frame exposes its visible choices
  directly before Response; and
- a long Memory may open a nested reading layer, but its stable section UID
  and outer position do not change.

Each section also declares which rendered fragments express that stop. An
overview normally focuses both its heading and prose: the heading uses the
bold blue identity style while the prose uses the same blue foreground without
bold. An operation may set `focus_body=False` when its body is contextual
chrome rather than part of the independently reviewable claim. This visual
scope never creates another navigation stop.

Review-item headings remain bold even when another section owns focus; focus
changes their foreground from neutral white to blue. The collection heading is
bold report chrome, while each item is its own navigation stop. This keeps the
kind and title legible without falsely making the whole collection one target.
Generic exact-results headings use the same resting and focused label policy;
their result rows retain their own Memory or outcome semantics.

The common Resolution model also lets an operation declare whether its generic
exact-results block is semantically present. An empty but meaningful result set
may still render `(none)`. Atomize hides that block because its projected
children remain source-linked inside each finding and its complete projection
count is reported separately; showing `EXACT RESULTS · 0` would incorrectly
suggest that the analysis projected no Memories.

Terminal width may change the number of visual rows inside a nested reading
layer. It must never change the number or identity of outer semantic stops.

## Operation declarations

`ResolutionWorkbenchView` accepts typed `ResolutionOverviewSection` records.
Adapters choose their own meaningful boundaries:

- Atomize declares `UNDERSTOOD`, `CHANGED`, and `UNRESOLVED`;
- Meld declares `UNDERSTOOD` and `ACCOUNTING`;
- Sever declares `UNDERSTOOD` and, when applicable, `NOT INCLUDED`;
- Update declares one `PLAN` section;
- Forget declares one `ASSESSMENT` section; and
- read-only Review reports declare one `SUMMARY` section.

The legacy flat `overview` remains available for snapshots and compatibility,
but live navigation uses the typed sections when supplied. Legacy callers get
one compatibility `UNDERSTOOD` stop rather than having their prose split by a
heading parser.

Result already stores `understood`, `happened`, and `unresolved` as distinct
typed sections. The Result shell now exposes all three before its individual
cases, and an expanded case contributes a detail header, each operation-owned
detail block, and its trace as separate stops.

Compare and Share use the same controller while retaining their separate
documents and pane topology. Compare still recognizes its trusted renderer's
operation-owned headings when constructing a document; removing that
compatibility projection requires changing the persisted Compare report
builder and is intentionally separate from the focus-control contract.

## Nested Memory reading

Actionable evidence previously generated `SOURCE_MEMORY_LINE` section UIDs.
Those UIDs encoded the current wrapping and therefore changed after resize.
The outer section is now `SOURCE_MEMORY` and is keyed by the item, evidence,
claim, and Memory identities. Enter opens the controller's process-local
nested reading index. Up/Down then moves the viewport anchor among rendered
rows while the outer Memory remains the only semantic stop. Enter, Escape, or
Backspace closes the nested layer.

This state is presentation-only. It never enters an operation artifact,
response, provider input, or exact command receipt.

## Boundaries

The shared controller does not authorize actions or imply that all section UI
is one workflow. Ground exact-command approval, writable composers, Context
pickers, and operation-specific option validation keep their existing state
machines. They may reuse low-level focus blocks or navigation primitives where
appropriate without inheriting Resolution actions.

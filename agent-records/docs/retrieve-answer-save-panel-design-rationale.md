# Retrieve & Answer shared SAVE design rationale

## Motivation

Find, Search, and Query are the three `SEARCH & EXPLAIN / RETRIEVE & ANSWER`
operations. Their interactive outcomes previously diverged: Search exposed
separate `SAVE AS`, parent-browser, Save Location, and `TO DO` frames, while
Find and Query had no durable outcome action. `PARENT CONTEXT` also described
an implementation mechanic rather than the person's goal. The three operation
packages are independent even though this is the narrowest catalog family in
which their common result interaction belongs.

## Package boundary

The canonical console packages are
`memcommit.adapters.console.commands.{find,search,query}`
and the corresponding application packages are
`memcommit.application.operations.{find,search,query}`.
The shared SAVE composition lives under
`memcommit.adapters.console.terminal.components.retrieve_answer_save`;
operation-neutral exact-name, Context-tree, selection, focus, frame, and
palette mechanics remain in their narrower shared terminal components. Shared
readable Source-name resolution lives under
`application.capabilities.save_context_from_selection.source_resolution`.
Application code never imports the console component.

## Visible SAVE contract

One conditional `SAVE` frame appears after a completed, nonempty Find/Search
result or a completed Query answer. It presents one vertical grammar:

- `CONTENT` identifies the exact completed outcome being saved.
- `MODE` appears only when existing Memories are retained.
- `LOCATION` is one directly editable, require-new local Context name.
- `BROWSE` transiently expands the frozen local Context tree inside the same
  frame and places the current final name segment beneath the chosen row.
- `ACTION` is the one reviewed save edge.

`PARENT CONTEXT`, `REPARENT`, separate Save As and To Do boxes, and a hidden
destination hierarchy are intentionally absent. Browse does not create, load,
switch, rename, or persist a Context. The exact operation-supplied validator is
authoritative at the Action edge.

## Application semantics and authority

Find and Search both adapt exact checked result rows to
`application.capabilities.save_context_from_selection`. COPY creates fresh
Memory identities, REFERENCE retains immutable snapshots, and EMBED creates
live read-only relationships. The capability resolves every selected Source
through the frozen readable catalog and calls
`authorize_context_use(access, ContextUse.READ)` before publication; Grant
locks only close revision races. Sources remain unchanged and the destination
must be a new local Context.

Query does not use the selected-Memory capability. Its generated answer is an
already disclosed operation output, not an existing Source Memory. Query owns
a separate typed `SaveQueryAnswerRequest` and creates one new Memory containing
the complete answer. It records the question and public Source description in
the checkpoint without reopening concealed QUERY-only material or fabricating
Memory lineage to evidence.

## Alternatives and limitations

A generic terminal Save Location editor was rejected as the owner of the whole
panel because `CONTENT`, optional `MODE`, and `ACTION` are specific to the
Retrieve & Answer family. Three operation-local panels were rejected because
their focus topology and Browse behavior would drift. Treating Query answers
as COPY or REFERENCE selections was rejected because that would falsely claim
an existing Memory identity.

The Query save currently persists the rendered complete answer as one Memory;
typed answer References remain checkpoint provenance rather than durable
MemoryRef items. Save is interactive-only in this change; existing one-shot
Find, Search, and Query output remains read-only unless a future explicit CLI
operand defines the same reviewed contract.

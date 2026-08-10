# Source projection display design rationale

## Motivation

Readable source facts were already preserved by storage and authority code, but
terminal surfaces described them with operation-owned strings such as `READ
GRANT`, `GRANTED VIEW`, `[query-only]`, `ref`, and `Memory reference`.  That
made the same object look different in Switch, Find, Query, endpoint setup,
List, Show, and Status.  One Find guard also compared the rendered `READ GRANT`
text to decide whether materializing a reference was allowed, so changing copy
could change behavior.

The common Context tree renderer previously standardized only row geometry,
escaping, selection, and focus.  Its untyped `annotation` string intentionally
left meaning to callers, but that boundary proved too weak once authority,
traversal, and pointer forms could appear together.

## Typed display contract

`memcommit.source_projection` preserves four independent axes:

- access: `OWNED`, `READ GRANT`, or `QUERY GRANT`;
- reach: `DIRECT`, `DESCENDANT`, or `VIA EMBED`;
- form: `CONTEXT`, `MEMORY`, `MEMORY REF`, or `QUERY VIEW`;
- state: `READ ONLY`, `UNAVAILABLE`, `DANGLING`, `CYCLE`, or `NOT INCLUDED`.

The typed form remains part of the source record, but presentation separates
an object's ordinary name from its source annotations. Compact object names
are `context`, `memory`, `memory ref`, and `query view`; detail headings use
`Context`, `Memory`, `Memory ref`, and `Query view`. Access, optional Grant
permissions, reach, and state remain uppercase annotations in that order.
Thus an object row is rendered as `[memory UID]`, followed separately by facts
such as `READ GRANT`, `VIA EMBED`, or `READ ONLY`. A dense Context tree omits
the redundant `context` noun while retaining any non-default annotations.

This distinction prevents an ordinary object kind from looking like a status
badge and preserves the established compact `memory`/`context` grammar.
`memory ref` names the durable pointer object. `Referenced` would instead
describe the target Memory's incidental state and could be mistaken for an
answer citation or another semantic link. `query view` names an opaque query
route; it does not imply that ordinary Memory content was opened.

## Presentation invariants

- All plain CLI and prompt-toolkit labels derive from the same typed facts.
  The common presentation module owns both the object-name projection and the
  annotation projection; commands must not recreate either vocabulary.
- Object-list rows keep the object name adjacent to the UID. Access, reach,
  and state remain annotations rather than being inserted into that identity
  label. Detail headings and operation frame titles may use title or heading
  case without changing the compact object-name policy.
- Context and report text remain neutral.  Memory bodies remain lavender,
  compact reference-form tokens remain purple, and availability states use the
  warning color.  A selected or focused control's common blue treatment
  overrides token colors so one row never appears to have two keyboard owners.
- Terminal escaping occurs after semantic tokenization.
- Narrow Memory previews wrap their content after the complete source label;
  provenance labels are not shortened independently into ambiguous text.
- Raw string annotations remain a compatibility input for callers not yet
  migrated, but new source-aware callers pass typed facts.

## Authority boundary

Display is a one-way projection of authority state.  Permission, loading,
materialization, and mutation decisions must use `ContextAccess`, frozen Grant
bindings, or other typed receipts.  They must never inspect a rendered label.
In particular, Find receives the frozen set of granted public Context names
separately from the annotations it renders.

The display model does not authorize traversal, resolve MemoryRef targets,
open QUERY-only content, or turn Grant attachment metadata into a hierarchy
edge.  Those responsibilities remain with the readable catalog and the
calling operation.

## Migration and compatibility

The initial migration covers the common Context tree, shared Context picker,
session endpoint setup, Switch, Contexts, Find, Query, List, Show, Status,
Compare retention, Translate, History/restoration, Delete, and Merge displays.
Saved session schemas and storage records are unchanged.  Remaining
explanatory prose can move incrementally when it represents one of these typed
facts; compatibility strings should not gain new semantic branches.

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
`memory ref` remains the compatibility object name where a consumer has not
classified the pointer's time semantics. A typed compact relationship row uses
`embedded` for a live Memory link and `reference` for an immutable snapshot;
those nouns describe durable behavior, not the target Memory's incidental
state. `query view` names an opaque query route; it does not imply that ordinary
Memory content was opened.

List and Show place Memory Source identity before content so a person can scan
ownership before reading a long body:

```text
[embedded 6bd4bcf0] [practice/3][memory ca562047] current Source text  READ ONLY
[reference dbdb4436] [practice/3][memory ca562047] retained snapshot text  READ ONLY
```

The first UID belongs to the read-only relationship row; the second identifies
the directly owned Source Memory. This order also makes `CONTEXT:UID` available
as an executable Edit locator without presenting the relationship UID as the
writable object. The live row may change when its Source changes; the immutable
row retains its reviewed content.

## Compact Reference rows

Query answers and provider-free Find results share one typed Source projection
without sharing their application models. The common renderer supports two
explicit arrangements over the same facts:

```text
Query: [N] content — UID prefix, Context[, alias][ → Source UID prefix, Source Context]
Find:  N [UID prefix] content, [Context mX][ → [Source UID prefix] [Source Context]]
```

When complete content already ends in sentence punctuation, Find does not add
a second comma before the location bracket; the stored punctuation remains
unchanged.

`SourceReferenceRow` owns only display facts: a positive ordinal, content,
owner UID and Context, an optional operation-supplied alias, and optional
complete MemoryRef Source provenance. `render_source_reference_row` folds
stored whitespace into one logical row and owns both arrangements and their
punctuation. It does not assign citation numbers, invent aliases, search, rank,
limit a result set, or interpret exact match spans.

This separation is deliberate. Query assigns `[N]` by first citation use while
its `mN`/`cN`/`xN` alias identifies a position in a frozen evidence frame, so
`[1] ... , m5` is valid. Literal Find assigns the leading ordinal by stable
match order and `mX` by position in the complete frozen searchable corpus.
Those numbers therefore need not agree: the first match may correctly end in
`m5` when four earlier searchable Memories did not match. A Find MemoryRef
displays the pointer owner's UID and Context first, followed by `→` and the
referenced Source identity; compact output must not make the content's Source
look like the owning item.

The base row is logical rather than width-truncating and never silently drops
content. A caller may request a bounded content preview; the renderer then
marks the omission with `…` before the complete provenance suffix.
Provider-free Find deliberately does not request that option: plain output,
compact paging, the explicit workbench, clipboard output, and machine
projections all retain complete folded content. A terminal may wrap a long
logical Source row onto multiple physical lines. Find's ten-row page size
remains a separate operation-owned policy over a complete typed result.
The operation-neutral `paged_result` shell owns only focused index, discrete
page range, `SHOWING a–b OF total`, navigation, and primary-screen close
mechanics; it never owns Source identity or matching. Query's used-citation
set, Find's complete span set, `--all-results`, and clipboard scope remain outside both
shared presentation components.

Reusing Query's `FindAnswerEvidence` directly in literal Find was rejected.
That would impose Query's alias grammar and evidence kinds on a provider-free
exact-text operation, and would make a presentation refactor capable of
changing either operation's semantic result contract.

## Presentation invariants

- All plain CLI and prompt-toolkit labels derive from the same typed facts.
  The common presentation module owns both the object-name projection and the
  annotation projection; commands must not recreate either vocabulary.
- Object-list rows keep the object name adjacent to the UID. Access, reach,
  and state remain annotations rather than being inserted into that identity
  label. Detail headings and operation frame titles may use title or heading
  case without changing the compact object-name policy.
- Context and report text remain neutral. Standalone Memory bodies remain
  lavender; compact Source Reference rows remain neutral like Query citations.
  On typed List and Show relationship rows only the trusted `embedded` noun is
  yellow and only the trusted `reference` noun is mauve; UIDs, Source names,
  Memory bodies, and annotations stay in their existing styles. Availability
  states use the warning color. A selected or focused control's common blue
  treatment overrides token colors so one row never appears to have two
  keyboard owners.
- Terminal escaping occurs after semantic tokenization.
- Compact Reference row content is folded before adapter-owned terminal
  escaping; untrusted content cannot create a sibling ordinal or provenance
  line, while terminal controls remain the displaying adapter's boundary.
- Narrow Memory previews wrap their content after the complete source label;
  provenance labels are not shortened independently into ambiguous text.
- Raw string annotations remain a compatibility input for callers not yet
  migrated, but new source-aware callers pass typed facts.
- Sever's Source/Criteria setup is a typed consumer even though its three-pane
  composition remains operation-owned. It accepts the same
  `SourceDisplayValue` contract as Switch and the shared endpoint shell,
  validates through the common normalizer, and adds `UNAVAILABLE` as a typed
  state. This prevents a READ/QUERY Grant annotation migration from making
  `N → New Sever` fail before the setup screen opens. Stringifying at the
  Sever boundary was rejected because it would discard semantic token roles
  and recreate an operation-local annotation grammar.

## Authority boundary

Display is a one-way projection of authority state.  Permission, loading,
materialization, and mutation decisions must use `ContextAccess`, frozen Grant
bindings, or other typed receipts.  They must never inspect a rendered label.
In particular, Find receives the frozen set of granted public Context names
separately from the annotations it renders.

A granted Context remains a read-only projection even when its Grant permits a
command to mutate the authority-owned target. Status therefore renders both the
complete permission set and `READ ONLY`; omitting the permissions makes a
successfully writable operation target look categorically immutable.

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

# Readable Context namespace design rationale

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Motivation

An authority grant is intentionally stored in the Profile registry rather than
as a persisted child in the grantee's `context.json`. Revocation and grant
revision must therefore remain authoritative. The earlier read commands each
reconstructed part of that virtual topology independently: exact granted names
worked, but a recursive operation rooted at a local ancestor saw only the local
`MemoryStore` catalog. A granted public name such as `task-1/campus-wiki` could
therefore appear in Switch while `mem ls -R task-1` and `mem find --context
task-1` silently omitted it.

Grant attachment and public namespace membership are different relationships.
The attachment identifies which local Context authorizes the view; it is not a
semantic parent edge. The public name determines navigation. A grant attached
to `task-1/participant/construction-updates` may consequently expose
`task-1/campus-wiki` as a sibling branch under the public `task-1` namespace.

## Decision

`ReadableContextCatalog` freezes one command-local public namespace containing
ordinary local Context names and effectively READ-granted public names. Every
name retains an exact `ContextAccess` binding. Local names load through the
active `MemoryStore`; granted names load through a grant-bounded
`GrantedReadStore`. Commands may therefore traverse one namespace without
collapsing storage ownership, grant identity, or authorization.

The implementation is owned by
`memcommit.application.context_access.readable_contexts`. Constructing
the namespace reads the active Profile and Store, resolves exact
`ContextAccess`, revalidates Grant attachments, and routes Context loads across
local and authority stores. Those are application access decisions rather than
core name-resolution mechanics. Pure lexical expansion remains in
`core.context_targeting.resolution`, and ordinary on-disk Context listing
eligibility remains in `persistence.store.context_memory.context_listing_eligibility`.

The catalog observes these invariants:

- canonical public names, not grant attachments, determine lexical hierarchy;
- a local Context always remains locally owned and a granted Context always
  retains its authority Profile, grant UID/revision, attachment, and frozen
  resource binding;
- a narrower QUERY-only override is absent from the readable catalog and is
  represented only as an opaque name route where its canonical parent is
  visible;
- stale, ambiguous, or unauthorized grant bindings are never guessed during
  enumeration;
- query-only source content and authority checkpoint history are never opened;
- namespace projection is process-local and never writes grant pointers into a
  Context record.

The attachment still has one narrow read-time consequence. A local Context's
static inspection presents its directly attached top-level READ grants as
available Context source rows. A loader asked to follow embeds resolves those
displayed rows through their frozen `ContextAccess` bindings, so a recursive
read of that exact workspace does not show an empty shell while an exact read
of the displayed granted name has content. The rows do not become lexical
children, are absent when embed traversal is excluded, and QUERY-only grants
remain opaque routes rather than ordinary content contributors.

`mem ls`, current-state `mem find`, `mem rationale`, and the A/B source picker
for new symmetric `mem meld` sessions consume this shared catalog. Recursive
listing, search, Rationale target selection, and Meld source selection from `task-1`
can therefore see both
`task-1/participant/...` and `task-1/campus-wiki/...`, even when the latter is
stored by another Profile. Find also performs one bounded relevance check over
omitted first-level branches when a small global limit would otherwise show
material matches from only one sibling branch. `--direct` still excludes
namespace descendants and does not turn a virtual query route into a direct
item. Search always uses this current-readable boundary and never interprets
query wording as permission to traverse history. Rationale likewise uses only current Memories for a
granted contributor; it never treats READ as permission to inspect that
contributor's authority history.

Bare Rationale labels its first target control `PROFILE`, so it uses
`freeze_profile_readable_context_catalog`: an empty current Context is only the
initial location, never the namespace boundary. The selector therefore keeps
ordinary local Contexts and every valid READ-granted public Context visible.
After one location is chosen, its exact/subtree Memory range uses that same
frozen catalog; a granted selection retains its exact access and Grant receipt.
An explicit `--context` remains intentionally narrower and starts directly in
that Context's exact/subtree selector.

## Safety and limitations

The catalog is a read view, not a cross-store transaction or a merged Context.
Mutation commands must continue to resolve and lock the exact owning store.
Provider-backed operations must continue to apply their operation-specific
disclosure and combination rules; a readable name alone does not authorize a
derived save or cross-authority mutation.

Rationale checks that boundary before connecting to its provider. Inference
within one exact granted resource remains a READ-only, current-state
interpretation. If a public subtree combines local and granted ownership, or
combines distinct grants, every contributing Grant must additionally permit
`DERIVE` and `COMBINE`. Missing permission fails closed before any candidate
content is sent. Query-only routes remain excluded from the inference frame.
Meld similarly annotates granted source rows, excludes query-only routes, and
keeps C local. Its current directional mode remains local-only and reports that
boundary if a visible granted source is selected.

A recursive list rooted locally can contain both local and granted Memory
content. `mem ls -R --copy` may copy exactly that authorized rendered scope as
plain text whether the granted contributor entered through public lexical
placement, a persisted Embed, or one displayed attached READ projection. This
is an explicit user-controlled disclosure, not a durable or replayable
multi-grant receipt; QUERY-only content remains excluded.

This rollout does not make every operation picker grant-aware. Some
creation workflows intentionally accept only ordinary owned Contexts. Those
pickers must adopt the catalog only when their operation contract permits a
granted endpoint.

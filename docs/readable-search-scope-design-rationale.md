# Readable ordinary search-scope design rationale

## Problem

Find and ordinary-Context Query both construct a searchable frame from one or
more ordinary Context roots. Query imported private functions from the Find
command, while the interactive Find workbench independently added multiple
roots and separated lexical descendants from embedded graph traversal. The
private dependency hid a real shared boundary and made it easy for one caller
to change disclosure scope accidentally while refactoring another.

## Decision

`memcommit.context_targeting.search` owns two operation-neutral steps:

1. `load_readable_search_roots` validates ordinary roots, optionally expands
   canonical lexical descendants, independently chooses direct loading or
   embedded-Context traversal, and deduplicates loaded Context identities.
2. `collect_readable_search_candidates` collects the ordinary searchable
   items from those roots and adds profile-local activity artifacts only for
   roots that the caller explicitly marks as artifact-authorized.

The module accepts a narrow ordinary-Context store protocol implemented by
`MemoryStore`, `GrantedReadStore`, and `ReadableContextCatalog`. It does not
connect a provider, rank results, synthesize an answer, render operation UI, or
decide authority. Find continues to own current-versus-history routing,
related-result fallback, and multi-target behavior. Query continues to own
grounded evidence selection and answer synthesis.

The interactive Find caller supplies its frozen `ReadableContextCatalog` so
each selected public name resolves through the exact local or Grant-bound
store. It separately filters artifact roots to local access. Ordinary Query
keeps its established store boundary: a local query uses its local
`MemoryStore`, while an exact granted query uses `GrantedReadStore`. Moving the
helper therefore removes the private import without silently widening Query
to newly visible granted namespace branches.

## Boundaries

Lexical descendants and embeds are independent axes. A name below `task-1/`
is in namespace reach even without an embed edge; an embedded Context can be
outside that prefix. `include_descendants` controls the first axis and
`follow_embeds` the second. Overlaps are deduplicated first by Context UID and
then by the existing candidate collector's logical item identity.

Query-only routes are intentionally excluded from this protocol. Their public
names may be projected into authorized ordinary views, but their concealed
content is accessible only through the dedicated Query interface. They cannot
be passed as ordinary roots, loaded directly, or made traversable merely by
enabling embeds. This module grants no `DERIVE`, `COMBINE`, export, history, or
mutation authority; every provider-backed or consequential operation must
retain its own permission checks and exact access bindings.

Compatibility adapters remain temporarily in `find.py` for tests and retained
internal callers that referenced the former private helpers. New cross-command
code must import the shared module rather than those aliases. Canonical lexical
name expansion itself lives in `context_targeting.resolution`, shared with the
merged Context loader without coupling search artifacts to saved-session code.

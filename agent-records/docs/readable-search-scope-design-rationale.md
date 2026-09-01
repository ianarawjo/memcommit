# Readable ordinary search-scope design rationale

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Problem

Find and ordinary-Context Query both construct a searchable frame from one or
more ordinary Context roots. Query imported private functions from the Find
command, while the interactive Find workbench independently added multiple
roots and separated lexical descendants from embedded graph traversal. The
private dependency hid a real shared boundary and made it easy for one caller
to change disclosure scope accidentally while refactoring another.

## Decision

`memcommit.application.capabilities.retrieval_corpus` is the operation-neutral
owner of the readable candidate corpus shared by Search, Find, and ordinary
Query. Provider-free `RetrievalCandidate` and `RetrievalArtifact` values plus
graph collection live in `candidates.py`; store-backed bounded projections live
in `artifacts.py`; readable loading lives in `loading.py`. Search prompting,
decoding, budgeting, and reranking remain separately owned by Search's
`ranking.py`:

1. `load_readable_corpus_roots` validates ordinary roots, optionally expands
   canonical lexical descendants, independently chooses direct loading or
   embedded-Context traversal, and deduplicates loaded Context identities.
2. `collect_readable_corpus_candidates` collects the ordinary searchable
   items from those roots and adds profile-local activity artifacts only for
   roots that the caller explicitly marks as artifact-authorized.

The module accepts a narrow ordinary-Context store protocol implemented by
`MemoryStore`, `GrantedReadStore`, and `ReadableContextCatalog`. It does not
connect a provider, rank results, synthesize an answer, render operation UI, or
decide authority. Search owns current-readable ranking, related-result fallback,
and multi-target behavior; explicit `mem log QUERY` owns retained-history
planning. Query continues to own
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
enabling embeds. This shared corpus capability grants no `DERIVE`, `COMBINE`, export,
history, or mutation authority; every provider-backed or consequential
operation must retain its own permission checks and exact access bindings.

Store-backed activity projection likewise cannot import a console session
picker. Compare evidence enters through Compare's terminal-independent session
reader. Meld evidence loads only the exact latest slots keyed by target Contexts
in the frozen local artifact frame, so an unrelated malformed Meld record is
neither disclosed nor made a precondition for Search or ordinary Query.

Thin compatibility facades remain under `application.operations.search` for
the former `candidates`, `corpus`, and `artifacts` imports. Production Find,
Search, and Query code imports the shared capability directly; the facades own
no behavior. Canonical lexical name expansion itself remains in
`context_targeting.resolution`, shared with the merged Context loader without
making retrieval artifacts part of core targeting.

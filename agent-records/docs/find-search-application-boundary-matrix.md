# Search application-boundary matrix

Last reviewed: 2026-08-25.

## Purpose

Search is the next read-only vertical slice after Summarize and Sever. It
tests whether one application use case can serve the plain CLI and interactive
search workbench while preserving readable Context targeting, local-only
activity artifacts, query-view privacy, and the current-state-only contract.

Search and result materialization remain two separate use cases. The
conversational Search controller, answer synthesis, and broader-scope
confirmation remain outside both. Public Python and the versioned agent/MCP
adapter now enter the same typed Search application rather than invoking the
CLI or reconstructing its semantics.

## Intended call path

```text
plain mem search QUERY ----------\
interactive Search workbench ----+--> SearchRequest
MemCommitClient.search ----------+
agent/MCP memcommit_search ------/          |
                                            v
                              run_search
                              (application)
                                            |
                            SearchSourcePort
                                            |
                       MemoryStoreSearchSourcePort
                              (runtime adapter)
                                            |
                          SearchResponse
                               /           \
                       CLI presenter     TUI presenter
```

The application module imports no command, Typer, prompt-toolkit, clipboard,
or materialization code. The Search command package owns its workbench and
shared result presenter, while those adapters import request and response
types from the application owner directly. The former interface presenter path
is removed rather than retained as an inverse compatibility facade.

## Package ownership

The canonical semantic Search vertical now lives under
`memcommit.application.operations.search`. `application.py` and `runtime.py` own the
provider-backed read-only analysis request, frozen readable Source, ranking,
and current-result execution. `materialization_application.py` and
`materialization_runtime.py` own the separately reviewed COPY/REFERENCE
request, live-source and authority revalidation, require-new publication,
checkpoint, rollback, and receipt. Co-location makes the vertical discoverable
without allowing analysis to publish or materialization to rerun inference.

The historical `memcommit.find_application`, `memcommit.find_runtime`,
`memcommit.find_materialization_application`, and
`memcommit.find_materialization_runtime` paths remain behavior-free
module-identity aliases. Old imports, monkeypatch targets, and serialized
globals resolve to the canonical modules, while importing
`memcommit.application.operations.search` alone remains lazy.

This package is intentionally separate from provider-free Find under
`memcommit.application.operations.find`. The relocation changes no readable authority,
provider disclosure, ranking, current-only result, selection, materialization,
checkpoint, rollback, or public projection behavior. The current-only Search
work and its removal of implicit temporal routing remain in the same canonical
analysis owner rather than becoming compatibility-facade behavior.

## Boundary matrix

| Boundary | Application contract | Runtime implementation | Interface responsibility | Invariant |
| --- | --- | --- | --- | --- |
| Request | `SearchRequest` | CLI and workbench adapters construct it | Resolve argv or the shared compact Scope's exact direct input/transient Browse state into exact public target names and explicit reach booleans | At least one distinct target, nonblank query, and limit 1–20 |
| Current source | `FrozenSearchCurrentSource` | `MemoryStoreSearchSourcePort.freeze_current` | None after request construction | Readable roots and candidates are frozen before provider construction |
| Provider | `SearchProviderFactory` | Injected configured provider factory | CLI may project typed progress; TUI owns its background indicator | Construction occurs only after source freezing; query-only content is never opened |
| Current execution | `run_search` + `rank_candidates` | Shared semantic TOP_K_RERANK planner | Present typed rows only | One frozen candidate frame; lexical-branch supplementation reuses the same provider and never invents candidates |
| Result | `SearchResponse` / `SearchResult` | `execute_search` | Plain and TUI projections may differ without rerunning | Response retains the exact request and CURRENT evidence |
| Durable effect | None | None | Search adapters only present results or construct a separate materialization request | Searching does not create, mutate, switch, copy, or persist a Context |
| Public projection | `SearchResult` / `SearchItemResult` | `api._operations.search` resolves one frozen client Store/Profile boundary | Python returns immutable DTOs; agent/MCP returns version-1 JSON with `effect: NONE` | Public routes call `execute_search`; they neither import the CLI nor own a second ranking path |

## Authority and disclosure matrix

| Case | Frozen evidence | Provider disclosure | Result behavior |
| --- | --- | --- | --- |
| Exact local Context | Exact readable root | Direct searchable items plus authorized local activity artifacts | CURRENT rows |
| Lexical descendants | Expanded public-name subtree | Candidates from every selected readable descendant | CURRENT rows with optional sibling-branch coverage check |
| Embedded Contexts | Resolved readable graph when requested | Resolved searchable items; cycles deduplicated by Context identity | CURRENT rows |
| READ Grant | Granted public projection | Authorized projected Memories and public query-view names; no active-Profile private artifacts | CURRENT rows |
| Query-only route | Public route name only | Name and opaque candidate alias; concealed source content is never loaded | QUERY row that remains a hint for a separate authorized Query operation |

Search has no prepared-result cache or durable search receipt in this
slice. Provider/model configuration and secrets remain owned by the existing
composition adapter. COPY/REFERENCE crosses a separate typed write boundary
and is intentionally not evidence that `run_search` mutates state.

## Materialization write boundary

```text
reviewed SearchResponse + checked rows + mode + destination
                               |
                               v
                 SearchMaterializationRequest
                               |
                               v
                  run_search_materialization
                    prepare -> materialize
                               |
                               v
             MemoryStoreSearchMaterializationPort
                               |
                               v
                  SearchMaterializationResult
```

| Boundary | Owner | Invariant |
| --- | --- | --- |
| Reviewed request | `SearchMaterializationRequest` | CURRENT results only; at least one unique checked Memory or resolved MemoryRef; complete frozen source identity; exact COPY/REFERENCE mode and destination |
| Prepared effect | `FrozenSearchMaterialization` | Opaque runtime token must retain the reviewed mode, destination, and source count |
| Live source | `MemoryStoreSearchMaterializationPort.prepare` | Context UID, Memory UID, and displayed content must still match; query, history, and artifact rows cannot enter the write |
| Authority | runtime derived-policy and `authorized_context_operation` | Granted COPY requires READ, DERIVE, EXPORT, SAVE_ANALYSIS, and COMBINE across multiple domains; REFERENCE remains local-only; Grant revision and permissions remain locked through publication |
| Destination | Store require-new creation | An existing or concurrently created owner is never overwritten; materialization never switches the current Context |
| Source freshness | local source lock set or external authority snapshot lock | Every successful receipt describes the exact source bytes used to construct the output |
| Output | COPY or REFERENCE | COPY creates fresh Memory UIDs; REFERENCE uses the ordinary live pointer primitive; both preserve checked ranked order and leave Source unchanged |
| Receipt | `SearchMaterializationResult` plus automatic `search` checkpoint | Context, checkpoint, and item identities must match the reviewed plan; the checkpoint retains query, mode, and source/output identities |
| Failure | Store rollback | A stale source, revoked authority, destination collision, or write failure publishes no partial Context or checkpoint |

The TUI owns selection and Save Location presentation only. Its setup order is
`SCOPE → SEARCH → RESULTS`: an exact readable Context is the direct fast path,
while Profile/multiple selection reveals the complete frozen tree only while
Browse is open. Search rows use `N [UID] complete content [Context · kind]`
with physical wrapping but no application-authored elision. Once its `TO DO`
row returns a materialization intent, the command adapter maps it to the typed
request and calls the runtime. It does not resolve source Memories, evaluate
Grant permissions, construct output items, or write a Context itself. The
command-owned `materialize_search_results` adapter reaches this application
path directly; there is no Find-named materialization facade.

## Verification

`tests/test_find_application.py` proves:

- terminal-independent current-readable execution, including queries that
  contain time-oriented words;
- authority/source freezing before provider construction;
- Search never enumerates retained history or changes mode from query wording;
- `agent-records/docs/screenshots/search-current-only-temporal-20260823/` records the
  corresponding 180×52 color-TTY entry, query, running, current-result,
  checked-result, and read-only-close states;
- direct query-view name disclosure without hidden source loading;
- granted current content follows the same current-only query contract;
- no stdout or stderr from the Store runtime; and
- no command, Typer, or prompt-toolkit imports in the application module.

`tests/test_search_materialization_application.py` proves:

- exact prepare-before-materialize sequencing and plan/receipt matching;
- CURRENT/Memory-only checked-set validation and duplicate-source rejection;
- selected-only COPY and live local REFERENCE behavior;
- source preservation, stale-source revalidation, and concurrent destination
  collision handling;
- checkpoint and partial-Context rollback after an injected write failure;
- export-authorized granted COPY and local-only REFERENCE;
- a typed TUI-to-application request with no direct persistence call; and
- no command, Typer, TUI, or provider import in the application module.

Existing Search, Search history, search-workbench, result-materialization,
source-projection, authority, and Context-operand tests remain the parity gate
for CLI and TUI adapters. Public-client, agent-registry, and MCP-projection
tests additionally prove the versioned external route. The earlier combined
focused run passed 324 tests. An
expanded run passed 476 tests after excluding one unrelated untracked
provider-policy test whose compatibility name and implementation specify Search=`terra/low`
and Query=`sol/none` while its assertion
expects those two policies in the reverse order.

The exact isolated commit tree also passed Ruff, the four application/runtime
module type checks, and 146 Search application, materialization, workbench,
history-search, dialogue, and projection tests. CLI-importing tests in that
isolated tree remain gated by a pre-existing repository mismatch: committed
Summarize code imports `declared_artifact_available`, while its implementation
is still outside `HEAD`. The larger workspace runs above included that existing
implementation; this Search slice does not absorb it merely to make an unrelated
commit self-contained.

## Remaining boundaries and non-goals

1. A Search result is a frozen moment-in-time search outcome. This slice does not
   re-open every source after semantic ranking, and it does not claim the
   source remained unchanged while the provider ran.
2. `execute_search` requires an already frozen readable catalog. The
   public operation adapter now owns Store/Profile bootstrap and stable typed
   errors; operation-specific provider configuration remains infrastructure.
3. The interactive workbench and result presenter are physically hosted under
   `memcommit.adapters.console.commands.search`; application data and execution
   remain outside that adapter owner.
4. Conversational refinement, answer generation, and outside-Context
   confirmation retain their existing controllers and must be extracted as
   separate use cases.
5. The version-1 agent/MCP contract exposes bounded semantic Search only. It
   does not expose the conversational refinement shell or materialization
   controls; those remain separate reviewed operations.

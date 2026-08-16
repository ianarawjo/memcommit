# Search application-boundary matrix

Last reviewed: 2026-08-16.

## Purpose

Search is the next read-only vertical slice after Summarize and Sever. It
tests whether one application use case can serve the plain CLI and interactive
search workbench while preserving readable Context targeting, local-only
activity artifacts, query-view privacy, and the separate temporal-history
contract.

Search and result materialization remain two separate use cases. The
conversational Search controller, answer synthesis, and broader-scope
confirmation remain outside both. Public Python and the versioned agent/MCP
adapter now enter the same typed Search application rather than invoking the
CLI or reconstructing its semantics.

## Intended call path

```text
plain mem search QUERY ----------\
interactive Search workbench ----+--> FindSearchRequest
MemCommitClient.search ----------+
agent/MCP memcommit_search ------/          |
                                            v
                              run_find_search
                              (application)
                                            |
                            FindSearchSourcePort
                                            |
                       MemoryStoreFindSearchSourcePort
                              (runtime adapter)
                                            |
                          FindSearchResponse
                               /           \
                       CLI presenter     TUI presenter
```

The application module imports no command, Typer, prompt-toolkit, clipboard,
or materialization code. `memcommit.commands.find_search_workbench` retains
compatibility imports for callers that historically obtained the request and
response types from that module, but it no longer owns them. New internal code
imports the application owner directly.

## Boundary matrix

| Boundary | Application contract | Runtime implementation | Interface responsibility | Invariant |
| --- | --- | --- | --- | --- |
| Request | `FindSearchRequest` | CLI and workbench adapters construct it | Resolve controls and argv into exact public target names and explicit reach booleans | At least one distinct target, nonblank query, and limit 1–20 |
| Current source | `FrozenFindCurrentSource` | `MemoryStoreFindSearchSourcePort.freeze_current` | None after request construction | Readable roots and candidates are frozen before provider construction |
| Temporal source | `FrozenFindHistorySource` | `MemoryStoreFindSearchSourcePort.freeze_history` | None after request construction | Granted READ views fail before provider construction because their authority history is not disclosed |
| Provider | `FindSearchProviderFactory` | Injected configured provider factory | CLI may project typed progress; TUI owns its background indicator | Construction occurs only after source freezing; query-only content is never opened |
| Current execution | `run_find_search` + `rank_candidates` | Shared semantic TOP_K_RERANK planner | Present typed rows only | One frozen candidate frame; lexical-branch supplementation reuses the same provider and never invents candidates |
| Temporal execution | `run_find_search` + `search_history` | Local `HistoryTimeline` construction | TTY may open the existing read-only history picker from returned local evidence | Only direct local durable history enters the semantic turn; MemoryRef and query-source content stay closed |
| Result | `FindSearchResponse` / `FindSearchResult` | `execute_find_search` | Plain and TUI projections may differ without rerunning | Response retains the exact request and either CURRENT or HISTORY evidence, never both for one row |
| Durable effect | None | None | Search adapters only present results or construct a separate materialization request | Searching does not create, mutate, switch, copy, or persist a Context |
| Public projection | `SearchResult` / `SearchItemResult` | `api._operations.search` resolves one frozen client Store/Profile boundary | Python returns immutable DTOs; agent/MCP returns version-1 JSON with `effect: NONE` | Public routes call `execute_find_search`; they neither import the CLI nor own a second ranking path |

## Authority and disclosure matrix

| Case | Frozen evidence | Provider disclosure | Result behavior |
| --- | --- | --- | --- |
| Exact local Context | Exact readable root | Direct searchable items plus authorized local activity artifacts | CURRENT rows |
| Lexical descendants | Expanded public-name subtree | Candidates from every selected readable descendant | CURRENT rows with optional sibling-branch coverage check |
| Embedded Contexts | Resolved readable graph when requested | Resolved searchable items; cycles deduplicated by Context identity | CURRENT rows |
| READ Grant | Granted public projection | Authorized projected Memories and public query-view names; no active-Profile private artifacts | CURRENT rows |
| Query-only route | Public route name only | Name and opaque candidate alias; concealed source content is never loaded | QUERY row that remains a hint for a separate authorized Query operation |
| Temporal local query | Local timelines for selected owners | Bounded history-search catalog | HISTORY rows with local recovery evidence |
| Temporal granted query | No timeline | No provider connection | Safe failure |

Search has no prepared-result cache or durable search receipt in this
slice. Provider/model configuration and secrets remain owned by the existing
composition adapter. COPY/REFERENCE crosses a separate typed write boundary
and is intentionally not evidence that `run_find_search` mutates state.

## Materialization write boundary

```text
reviewed FindSearchResponse + checked rows + mode + destination
                               |
                               v
                 FindMaterializationRequest
                               |
                               v
                  run_find_materialization
                    prepare -> materialize
                               |
                               v
             MemoryStoreFindMaterializationPort
                               |
                               v
                  FindMaterializationResult
```

| Boundary | Owner | Invariant |
| --- | --- | --- |
| Reviewed request | `FindMaterializationRequest` | CURRENT results only; at least one unique checked Memory or resolved MemoryRef; complete frozen source identity; exact COPY/REFERENCE mode and destination |
| Prepared effect | `FrozenFindMaterialization` | Opaque runtime token must retain the reviewed mode, destination, and source count |
| Live source | `MemoryStoreFindMaterializationPort.prepare` | Context UID, Memory UID, and displayed content must still match; query, history, and artifact rows cannot enter the write |
| Authority | runtime derived-policy and `authorized_context_operation` | Granted COPY requires READ, DERIVE, EXPORT, SAVE_ANALYSIS, and COMBINE across multiple domains; REFERENCE remains local-only; Grant revision and permissions remain locked through publication |
| Destination | Store require-new creation | An existing or concurrently created owner is never overwritten; materialization never switches the current Context |
| Source freshness | local source lock set or external authority snapshot lock | Every successful receipt describes the exact source bytes used to construct the output |
| Output | COPY or REFERENCE | COPY creates fresh Memory UIDs; REFERENCE uses the ordinary live pointer primitive; both preserve checked ranked order and leave Source unchanged |
| Receipt | `FindMaterializationResult` plus automatic `search` checkpoint | Context, checkpoint, and item identities must match the reviewed plan; the checkpoint retains query, mode, and source/output identities |
| Failure | Store rollback | A stale source, revoked authority, destination collision, or write failure publishes no partial Context or checkpoint |

The TUI owns selection and Save Location presentation only. Once its `TO DO`
row returns a materialization intent, the command adapter maps it to the typed
request and calls the runtime. It does not resolve source Memories, evaluate
Grant permissions, construct output items, or write a Context itself. The old
`materialize_find_results` function remains as a thin compatibility facade and
reaches this same application path.

## Verification

`tests/test_find_application.py` proves:

- terminal-independent CURRENT and HISTORY execution;
- authority/source freezing before provider construction;
- current-versus-history source separation;
- direct query-view name disclosure without hidden source loading;
- provider-free failure for granted temporal history;
- no stdout or stderr from the Store runtime; and
- no command, Typer, or prompt-toolkit imports in the application module.

`tests/test_find_materialization_application.py` proves:

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
2. `execute_find_search` requires an already frozen readable catalog. The
   public operation adapter now owns Store/Profile bootstrap and stable typed
   errors; operation-specific provider configuration remains infrastructure.
3. The interactive workbench is still physically hosted under
   `memcommit.commands`; only its application data and execution dependency
   point moved. Physical TUI relocation is a separate presentation change.
4. Conversational refinement, answer generation, and outside-Context
   confirmation retain their existing controllers and must be extracted as
   separate use cases.
5. The version-1 agent/MCP contract exposes bounded semantic Search only. It
   does not expose the conversational refinement shell or materialization
   controls; those remain separate reviewed operations.

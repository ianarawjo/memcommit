# Query callable boundary matrix

Last verified: 2026-08-15.

## Scope

This matrix closes the internal Query vertical slice after its three execution
contracts, provider policy, CLI presenter, and TUI workbench received explicit
owners. It classifies the callables that cross application, authority,
provider, durability, or public-interface boundaries. Pure private rendering
fragments and dataclass validation remain mechanically discoverable in their
owning modules and inherit that module's boundary unless named below.

## Curated callable matrix

| Callable | Owner / intended layer | Input and result | External effects | Authority, disclosure, cache, and receipt boundary | Production callers and evidence | State |
| --- | --- | --- | --- | --- | --- | --- |
| `operations.query.ordinary_application:run_ordinary_query` | application | `OrdinaryQueryRequest` -> `OrdinaryQueryResponse` | one injected provider completion at most | Source port freezes READable evidence and whole-frame preflight completes before provider construction; no cache, receipt, session, or write | ordinary runtime; `query-answer-application-boundary-matrix.md` | `VERIFIED` |
| `operations.query.ordinary_runtime:MemoryStoreOrdinaryQuerySourcePort.freeze` | infrastructure adapter | typed request -> frozen candidate frame | reads exact authorized Context projections | retains each frozen `ContextAccess`; query-only routes are excluded | ordinary runtime tests | `VERIFIED` |
| `operations.query.ordinary_runtime:execute_ordinary_query` | Store-backed application facade, internal | request + Store/catalog/provider factory -> response | Store reads and optional provider call | delegates semantic meaning to the application use case; no terminal dependency | CLI composition and Query TUI runner | `VERIFIED` |
| `operations.query.granted_application:run_granted_query_read` | application | `GrantedQueryRequest` -> `GrantedQueryReadOutcome` | injected authority read/provider use | required Query/Session authority freezes before provider construction; answer is withheld until Grant and Sources revalidate; optional publication remains process-local | granted runtime; `granted-query-read-publication-design-rationale.md` | `VERIFIED` |
| `operations.query.granted_application:publish_granted_query_session` | application | unpublished publication -> typed receipt | one injected session publication | publication is explicit and separate from reading; plan itself grants no write | granted runtime and CAS tests | `VERIFIED` |
| `operations.query.granted_runtime:freeze_granted_query_targets` | infrastructure adapter | Store -> public typed target tuple | reads Grant control-plane metadata only | never opens concealed Source content | Query TUI composition | `VERIFIED` |
| `operations.query.granted_runtime:execute_granted_query_read` | Store-backed application facade, internal | request + Store/provider/catalog loader -> outcome | authority/Source reads and optional provider call | preserves provider-before-concealed-Source ordering and post-call revalidation | runtime tests | `VERIFIED` |
| `operations.query.granted_runtime:execute_granted_query_session_publication` | Store-backed application facade, internal | publication plan + Store -> receipt | locked CAS session append | rechecks `SESSION_LOG`, Source identity, and record digest | runtime tests | `VERIFIED` |
| `operations.query.granted_runtime:execute_granted_query_request` | compatibility composition, internal | request + concrete dependencies -> response | may read and explicitly publish one requested turn | invokes the read use case and then the distinct publication use case; contains no alternate policy | CLI and Query TUI runner | `VERIFIED` |
| `operations.query.reference_application:run_query_reference` | application | `QueryReferenceRequest` -> `QueryReferenceResponse` | one provider query | constructs/authenticates provider before the Source port may open concealed content; no durable effect | reference runtime; `query-reference-application-boundary-matrix.md` | `VERIFIED` |
| `operations.query.reference_runtime:execute_query_reference` | Store-backed application facade, internal | request + Store/provider factory -> response | exact Query Source read and provider call | exact UID/name/language load; no terminal or session behavior | CLI legacy-reference route | `VERIFIED` |
| `infrastructure.providers.find_query:connect_ordinary_query_provider` | concrete provider composition | optional frozen non-secret config -> pinned provider | endpoint authentication/connection | Query defaults to Sol/none; timeout/model/reasoning injection is explicit and does not mutate CLI config | public client, Query command/TUI composition; provider-policy tests | `VERIFIED` |
| `infrastructure.providers.find_query:connect_query_route_provider` | concrete provider composition | persisted provider id + optional frozen config -> provider | endpoint authentication/connection | allowlisted adapter routing; legacy identifiers remain authoritative; non-Codex route policy is not overridden | public reference client and Query composition | `VERIFIED` |
| `api.client:MemCommitClient.query_ordinary` | public Python facade | question + exact Context operands/scope -> `OrdinaryQueryResult` | authorized Store reads and optional provider call | one current snapshot; explicit roots are local-only; no durable write; internal response is projected to stable typed citations | public API tests and root package exports | `VERIFIED` |
| `api.client:MemCommitClient.query_granted` | public Python facade | public route/question/session intent -> `GrantedQueryResult` | active-Profile authority reads, provider call, optional session CAS | successful session call includes separate publication; publication failure returns no partial success; concealed content/token never exposed | public API authority/session tests | `VERIFIED` |
| `api.client:MemCommitClient.query_reference` | public Python facade | `QueryContextRef` + question -> `ReferenceQueryResult` | provider authentication, exact concealed Source read, one query | provider is constructed before Source open; no durable write | public API ordering and preservation tests | `VERIFIED` |
| `interfaces.cli.query:split_query_memory_selector` | CLI adapter | selector -> view and optional opaque handle | none | exact syntax only; performs no route lookup or Source open | Query command; CLI adapter tests | `VERIFIED` |
| `interfaces.cli.query:render_ordinary_query_response` | CLI adapter | typed response -> terminal output | stdout | terminal-safe projection only | Query command; CLI adapter tests | `VERIFIED` |
| `interfaces.cli.query:render_granted_query_response` | CLI adapter | typed catalog/answer -> terminal output | stdout | catalog shows only opaque handles/placeholders; no concealed content recovery | Query command; CLI adapter tests | `VERIFIED` |
| `interfaces.cli.query:render_query_reference_response` | CLI adapter | typed response -> terminal output | stdout | terminal-safe projection only | Query command; CLI adapter tests | `VERIFIED` |
| `interfaces.cli.query:render_query_session_list` / `render_query_session` | CLI adapter | visible durable transcript models -> terminal output | stdout | does not reconstruct a provider turn or open Sources | Query command; CLI adapter tests | `VERIFIED` |
| `interfaces.tui.operations.query:run_query_workbench` | TUI adapter | frozen catalogs + injected application runners -> workbench result | terminal interaction and optional plain clipboard write | provider runners fire only after explicit submit; clipboard is presentation-only; no hidden mutation receipt | Query composition; ordered 180x52 trace and workbench tests | `VERIFIED` |
| `interfaces.tui.operations.query:project_query_answer_clipboard` | TUI projection | typed answer + focus/scope -> plain text | none until injected writer is called | derives from typed body/Reference document, never reparses wrapped terminal output | Query screen and clipboard tests | `VERIFIED` |
| `commands.query:_query_ordinary_context` | composition root during Typer rollout | resolved Context/question -> rendered response | Store read, progress, optional provider, stdout | resolves READ and freezes the catalog before calling the runtime; owns no semantic answer policy | `commands.query:cmd` | `VERIFIED IN PLACE` |
| `commands.query:_open_query_workbench` | composition root during Typer rollout | Store + initial public options -> terminal workbench | freezes public catalogs, reads visible transcript metadata, terminal/provider effects through injected runners | the TUI receives frozen public controls and application callables; Help is injected rather than imported by the screen | `commands.query:cmd` | `VERIFIED IN PLACE` |
| `commands.query:cmd` | CLI entry/composition root | argv/TTY -> selected Query route | route-dependent Store, terminal, provider, and optional session effects | owns overloaded route choice, errors/exits, progress, and concrete dependency wiring; does not implement Query semantics or screen rendering | Typer registration and Query CLI tests | `VERIFIED IN PLACE` |

## Operation summary

| Operation family | Entry points | Application request/result | Provider boundary | Durable writes | Interface verification | State |
| --- | --- | --- | --- | --- | --- | --- |
| Ordinary Context Query | Python API, CLI one-shot, Query TUI | public `OrdinaryQueryResult`; internal `OrdinaryQueryRequest` / `OrdinaryQueryResponse` | authority/source freeze and whole-frame preflight before one completion | none | typed public citations, CLI renderer, typed TUI Answer/Reference document, application and architecture tests | `VERIFIED` |
| Authority-granted Query | Python API, CLI catalog/answer/session, Query TUI | public `GrantedQueryResult`; internal request/read outcome/publication receipt | provider authentication before concealed Source; post-call Grant/Source revalidation | only explicit `SESSION_LOG` CAS publication | public high-level publication result, opaque presenters, TUI, authority/session tests | `VERIFIED` |
| Local `QueryContextRef` | Python API, CLI one-shot | public `ReferenceQueryResult`; internal `QueryReferenceRequest` / `QueryReferenceResponse` | provider authentication before exact concealed Source open | none | public and CLI safe projections plus ordering tests | `VERIFIED` |

## Deliberate remaining boundary

The first versioned Python facade is now bounded by
`query-public-python-api-design-rationale.md`: one frozen Store root and
provider config, three explicit Query methods, public result/error projection,
and high-level granted-session completion over an internally separate
publication. The agent tool schema, asynchronous cancellation, and an
overloaded convenience router remain deliberately unshipped. Granted Query is
also intentionally restricted to a client whose frozen Profile is still the
active Profile; changing that requires authority infrastructure that no longer
depends on one process-global registry lock.

The two command-local helpers remain composition functions rather than policy.
Moving them into the CLI presenter would be incorrect; moving them into a
bootstrap module is optional structural follow-up once provider/config and
Store construction have non-command owners. Their current location does not
prevent CLI or TUI reuse of the terminal-independent application use cases.

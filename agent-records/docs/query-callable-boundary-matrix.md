# Query callable boundary matrix

Last verified: 2026-08-26.

## Scope

Query exposes three one-shot routes: ordinary readable Contexts,
authority-granted Query Views, and legacy local `QueryContextRef` values. This
matrix classifies callables that cross application, authority, provider, or
public-interface boundaries. Query has no durability boundary.

Query's console-specific adapters are co-located under
`memcommit.adapters.console.commands.query`: `command.py` owns Store/catalog
composition and route selection, `presentation.py` owns non-interactive answer
output, and `workbench/` owns Query-specific process-local models, typed Answer
and clipboard projection, Query View scope, and the prompt-toolkit screen. The
former `commands/query/workbench.py` compatibility facade and
`interfaces/tui/operations/query` implementation paths are removed. Shared TUI
controls retain their existing owners. This is an ownership relocation only;
provider timing, authority, output text, focus behavior, and existing PTY
evidence are unchanged.

## Curated callable matrix

| Callable | Owner / layer | Input and result | Effects and boundary | Evidence | State |
| --- | --- | --- | --- | --- | --- |
| `operations.query.ordinary_application:run_ordinary_query` | application | request -> response | frozen READable evidence and whole-frame preflight before at most one provider completion; no write | ordinary application tests | `VERIFIED` |
| `operations.query.ordinary_runtime:MemoryStoreOrdinaryQuerySourcePort.freeze` | infrastructure | request -> frozen candidate frame | exact authorized Context reads; Query Views excluded | ordinary runtime tests | `VERIFIED` |
| `operations.query.ordinary_runtime:execute_ordinary_query` | Store facade | request + injected dependencies -> response | delegates one-shot meaning; no terminal or persistence dependency | CLI/TUI/public API | `VERIFIED` |
| `operations.query.granted_source:freeze_granted_query_source_binding` | infrastructure | public route -> frozen binding | provider-authenticated concealed Source load with digest and exact access identity | granted Source tests | `VERIFIED` |
| `operations.query.granted_source:load_authority_query_source` | infrastructure | authorized View -> complete concealed Source frame | opens only inside the provider-authenticated runtime and returns no Source through public adapters | granted Source tests | `VERIFIED` |
| `operations.query.granted_application:run_granted_query_read` | application | request -> response | QUERY freezes before provider construction; response withheld until Grant and Sources revalidate | granted application tests | `VERIFIED` |
| `operations.query.granted_runtime:freeze_granted_query_targets` | infrastructure | Store -> public target tuple | reads Grant control-plane metadata only | Query TUI tests | `VERIFIED` |
| `operations.query.granted_runtime:resolve_granted_query_target` | infrastructure | Store + public name -> exact target or none | resolves independently of current Context from Grant metadata and exact local attachment identity; opens no concealed Source | canonical CLI route tests | `VERIFIED` |
| `operations.query.granted_runtime:execute_granted_query_read` | Store facade | request + injected dependencies -> response | provider-before-Source order and post-call revalidation; no write | runtime/public API tests | `VERIFIED` |
| `operations.query.granted_runtime:execute_granted_query_request` | compatibility alias | same as read facade | identical one-shot execution; no publication stage | CLI/TUI tests | `VERIFIED` |
| `operations.query.reference_application:run_query_reference` | application | request -> response | provider construction before Source port; no durable effect | reference boundary tests | `VERIFIED` |
| `operations.query.reference_runtime:execute_query_reference` | Store facade | request + Store/provider -> response | exact UID/name/language concealed Source read | CLI/public API tests | `VERIFIED` |
| `api.client:MemCommitClient.query_ordinary` | public Python | question + Context scope -> result | one-shot typed answer/citations; no write | public API tests | `VERIFIED` |
| `api.client:MemCommitClient.query_granted` | public Python | public route + required question -> result | active-Profile authority read; answer only | public API tests | `VERIFIED` |
| `api.client:MemCommitClient.query_reference` | public Python | reference + question -> result | provider-before-Source one-shot read | public API tests | `VERIFIED` |
| `interfaces.agent.query:QueryAgentAdapter.invoke` | agent adapter | version-3 tagged JSON -> JSON-safe result/error | exact route mapping; no route guessing, catalog, or transcript result | agent tests | `VERIFIED` |
| `interfaces.agent.query:query_agent_tool_schema` | schema projection | none -> fresh version-3 schema | grants no authority and carries no Source data | agent tests | `VERIFIED` |
| `commands.query.presentation:render_ordinary_query_response` | CLI | response -> stdout | terminal-safe typed answer projection | CLI tests | `VERIFIED` |
| `commands.query.presentation:render_granted_query_response` | CLI | response -> stdout | terminal-safe answer only | CLI tests | `VERIFIED` |
| `commands.query.workbench:run_query_workbench` | TUI | frozen catalogs + runners -> result | process-local state, one provider turn after Enter, optional plain clipboard | workbench tests and 180×52 trace | `VERIFIED` |
| `commands.query.workbench:project_query_answer_clipboard` | TUI projection | typed answer + focus -> text | no effect until injected writer; never reparses terminal output | clipboard tests | `VERIFIED` |
| `commands.query:_open_query_workbench` | CLI composition | Store + public options -> workbench | freezes ordinary and Query View catalogs; injects runners and Help | Query command tests | `VERIFIED IN PLACE` |
| `commands.query:cmd` | CLI composition | argv/TTY -> explicit route or narrow question fallback | accessible ordinary/QUERY targets resolve before an unmatched single bare value can become a current-Context question; repeated roots and QUERY-only `--context` retain exact authority | CF-01 route regressions and Query CLI tests | `VERIFIED IN PLACE` |

## Operation summary

| Route | Entry points | Provider boundary | Durable writes |
| --- | --- | --- | --- |
| Ordinary Context Query | agent, Python, CLI, TUI | readable freeze and whole-frame preflight before completion | none |
| Authority-granted Query | agent, Python, CLI, TUI | authentication before concealed Source; post-call Grant/Source revalidation | none |
| Local `QueryContextRef` | agent, Python, CLI | authentication before exact concealed Source open | none |

The CLI ordinary route accepts repeated `--context` operands. It resolves all
of them from one current-Context snapshot, requires distinct public names,
checks granted DERIVE and cross-domain COMBINE authority before provider
construction, and passes only those exact names to the ordinary application.
The local attachment recovered for the legacy two-positional route is never an
ordinary request target.

## Deliberate limits

There is no overloaded public Python router, streaming API, asynchronous
cancellation, network host, or cross-Profile granted authority service. The
command retains target-first positional routing and its narrow unmatched
single-value question fallback only at its composition root.
Legacy `query-sessions/` records are outside every callable above: current
Query code neither loads nor migrates them.

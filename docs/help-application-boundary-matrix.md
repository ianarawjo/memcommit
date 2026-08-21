# Help application boundary matrix

## Closure statement

Every currently implemented Help route reads the same 62-operation semantic
catalog through a terminal-independent discovery boundary. Exact catalog
queries remain provider-free. The optional natural-language CLI route adds one
bounded provider-backed ID-selection turn, then renders only canonical catalog
copy. No Help route opens a Store or authority source, reads Memory content,
creates a session, executes a selected operation, or enters an Apply,
checkpoint, or Undo lifecycle.

| Route | Entry | Application path | Projection | Effect | Evidence |
| --- | --- | --- | --- | --- | --- |
| Plain `mem help` | `interfaces.tui.operations.help.inventory.cmd` in a non-TTY | `command_entries` takes `list_operation_help()` once | Plain alphabetized inventory plus CLI-owned forms, maturity tags, and canonical expanded details | None | `test_help_catalog.py`, `test_help_application.py` |
| Interactive `mem help` | Same command in a TTY | Same frozen application snapshot | Grouped/A–Z browser; shared Context/direct-Memory locator and key guide; collapsed maturity tags; expanded typed details | None | Help renderer tests, `docs/screenshots/mem-help-common-locators-controls-20260821/`, `docs/screenshots/mem-help-import-query-details-20260816/`, and the full reviewed sequence in `docs/screenshots/mem-help-reviewed-content-20260816/` |
| Natural-language `mem help REQUEST` | Same command with one positional request in TTY or non-TTY | `prepare_help_lookup` freezes and preflights the complete catalog before `connect_help_provider`; `execute_help_lookup` requires exactly three distinct exact IDs | Three existing collapsed Help rows in semantic order: `mem NAME`, summary, and `WHEN`; no ordinal, browser, why, confidence, forms, or generated prose | None | `test_help_lookup_application.py`, `test_help_lookup_cli.py`, `test_help_lookup_provider_policy.py` |
| Shell selection | Hidden `--emit-selection` route | Same frozen application snapshot | One interface-owned command template on stdout | None | Existing Help selection tests |
| Selected CLI detail | One `CommandEntry` from the snapshot | Catalog meaning already bound to the entry | Common meaning composed with registered CLI syntax | None | `test_help_catalog.py` |
| Python list | `MemCommitClient.list_operations()` | `_operations.help.list_operations` → `list_operation_help` | `HelpCatalogResult` of immutable DTOs, including compact typed-detail references | None | `test_help_public_api.py`, import-boundary tests |
| Python describe | `MemCommitClient.describe_operation(name)` | `_operations.help.describe_operation` → application exact lookup | One `OperationHelpResult` or `HelpInputError` | None | `test_help_public_api.py` |
| Python detail list/describe | `MemCommitClient.list_operation_details(name)` / `describe_operation_detail(name, id)` | Exact application detail lookup | Compact typed references or one complete comparison, limitation, access boundary, or semantic boundary | None | `test_help_public_api.py` |
| Agent list/describe/detail | `HelpAgentAdapter.invoke` | The corresponding public client method | Version-1 JSON-safe operation and individually addressable typed details; `effect: NONE` | None | `test_help_agent_adapter.py`, registry tests |
| MCP discovery/call | Default registry → `McpRegistryProjection` | Exact agent adapter above | Every tool carries compact detail references in `_meta`; only `TOOL_SELECTION` summaries enter the visible description; full content stays behind Help `describe-detail` | None | MCP projection and official-SDK stdio tests |
| Companion Skill | Installed Skill frontmatter and procedural body | Calls its registered agent/MCP tool; it does not execute Help | Frontmatter carries the trigger; the body may name a stable detail ID instead of copying its full payload | None until the selected tool is called | Add Skill contract and validator |

## Invariants

1. The application list is alphabetized, unique, immutable, and complete for
   all 62 visible public operations.
2. Describe accepts one exact public operation name and detail lookup accepts
   one exact operation-local detail ID; neither performs fuzzy, alias, case, or
   whitespace normalization.
3. Stable summary, flow, execution, effect, range, use-when, maturity, and typed
   detail meaning originates in `help_catalog`; adapters do not author
   substitute operation descriptions. Composite tools may own one reviewed
   composite use-when value. A Help maturity tag describes product scope and
   is not a route-classification state from the operation evidence ledger.
4. Every detail has a typed kind, stable operation-local ID, discovery role,
   and exact owner. `TOOL_SELECTION` requires a bounded one-line discovery
   summary; `ON_DEMAND` content is not injected into every tool description.
5. No generic notes bag or second prose registry exists. Full detail payloads
   are retrieved through the same application boundary by exact ID.
6. CLI forms, aliases, categories, and responsive layout remain interface
   values and do not enter Python or agent semantic records.
7. Bare CLI, Python, agent, and MCP Help must succeed without creating a
   missing Store and without constructing or calling a provider. Only a
   nonblank positional CLI request authorizes the bounded semantic selector.
8. Natural-language lookup freezes the complete catalog before provider
   connection; uses `gpt-5.6-sol` with reasoning effort `none`; declares
   `TOP_K_RERANK`; and publishes no partial or prefiltered result.
9. Lookup output is exactly three unique exact catalog names. The interface
   preserves their semantic order and supplies canonical summary and best-for
   copy only after validation, without ordinal labels; the model cannot add reasons, confidence,
   explanations, command forms, or prose. Semantic order is not randomized, so
   fitness and display-position effects remain an intentional study limitation.
10. Agent/MCP Help is discovery only. It cannot execute another tool or confer
   authority to do so.

## Intentional exclusions

Framework-generated `mem <operation> --help` syntax remains a Typer/Click
projection over registered commands. Static registration reads the canonical
one-line summary, but parser rendering is not a parallel application use case.
Per-operation wording review remains separate. A Skill may name a stable detail
ID and retain the minimum procedural consequence needed to avoid an unsafe or
wrong tool call, but it is host guidance rather than another
operation-description source.

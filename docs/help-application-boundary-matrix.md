# Help application boundary matrix

## Closure statement

Every currently implemented Help route reads the same 59-operation semantic
catalog through one terminal-independent discovery boundary. Interface syntax
and layout remain projections. Help has no Store, authority, provider, cache,
session, Apply, checkpoint, or Undo lifecycle.

| Route | Entry | Application path | Projection | Effect | Evidence |
| --- | --- | --- | --- | --- | --- |
| Plain `mem help` | `interfaces.tui.operations.help.inventory.cmd` in a non-TTY | `command_entries` takes `list_operation_help()` once | Plain alphabetized inventory plus CLI-owned forms | None | `test_help_catalog.py`, `test_help_application.py` |
| Interactive `mem help` | Same command in a TTY | Same frozen application snapshot | Existing grouped/ A–Z browser and selected detail | None | Existing Help renderer/TUI tests; no visual change |
| Shell selection | Hidden `--emit-selection` route | Same frozen application snapshot | One interface-owned command template on stdout | None | Existing Help selection tests |
| Selected CLI detail | One `CommandEntry` from the snapshot | Catalog meaning already bound to the entry | Common meaning composed with registered CLI syntax | None | `test_help_catalog.py` |
| Python list | `MemCommitClient.list_operations()` | `_operations.help.list_operations` → `list_operation_help` | `HelpCatalogResult` of immutable DTOs | None | `test_help_public_api.py`, import-boundary tests |
| Python describe | `MemCommitClient.describe_operation(name)` | `_operations.help.describe_operation` → application exact lookup | One `OperationHelpResult` or `HelpInputError` | None | `test_help_public_api.py` |
| Agent list/describe | `HelpAgentAdapter.invoke` | The corresponding public client method | Version-1 JSON-safe result; `effect: NONE` | None | `test_help_agent_adapter.py`, registry tests |
| MCP discovery/call | Default registry → `McpRegistryProjection` | Exact agent adapter above | Official tool schema/call envelope | None | MCP projection and installed stdio smoke |

## Invariants

1. The application list is alphabetized, unique, immutable, and complete for
   all 59 visible public operations.
2. Describe accepts one exact public operation name; it performs no fuzzy,
   alias, case, or whitespace normalization.
3. All stable semantic fields originate in `help_catalog`; adapters do not
   author substitute descriptions.
4. CLI forms, aliases, categories, and responsive layout remain interface
   values and do not enter Python or agent semantic records.
5. A Help call must succeed without creating a missing Store and without
   constructing or calling a provider.
6. Agent/MCP Help is discovery only. It cannot execute another tool or confer
   authority to do so.

## Intentional exclusions

Framework-generated `mem <operation> --help` syntax remains a Typer/Click
projection over registered commands. Static registration reads the canonical
one-line summary, but parser rendering is not a parallel application use case.
Per-operation wording review and agent workflow skills remain future work.

# Help application boundary matrix

Last reviewed: 2026-08-28.

## Closure statement

Every currently implemented Help route reads the same 66-operation semantic
catalog through a terminal-independent discovery boundary. Exact catalog
queries remain provider-free. The optional natural-language CLI route adds one
bounded provider-backed ID-selection turn, then renders only canonical catalog
copy. No Help route opens a Store or authority source, reads Memory content,
creates a session, or enters an Apply, checkpoint, or Undo lifecycle. The
interactive terminal adapter may hand one reviewed exact argv to a separate
child invocation after the Help browser and editor close; that child owns its
own operation lifecycle.

## Implementation ownership

The canonical terminal-independent Help implementation lives under
`memcommit.application.operations.help`. `application.py` owns exact, provider-free catalog
listing and detail lookup. `lookup_application.py` owns the frozen whole-catalog
semantic selection plan and validates the provider's exact three-name result;
provider connection remains outside the package in the terminal adapter.
Production CLI, Python, agent, and MCP routes import those owners directly.

The Help terminal adapter now has one physical owner under
`memcommit.adapters.console.commands.help`. `command.py` owns plain output and
the interactive browser, `command_handoff.py` owns the fixed-operation editor
and child argv launch, and `study_copy_guard.py` owns the Study-only input
guard. Reviewed translated operation Summary and
Best For copy lives beside the canonical English records under
`memcommit.operation_catalog.translations`, with
language selection in `operation_catalog.localization`. The 11 operation
families, their order, intent descriptions, optional complete family sections,
and translated family copy are owned by the same top-level catalog. The Help
application projects those records as renderer-neutral family groups; console
Help consumes that application grouping rather than rebuilding it.
Help-only concept, locator, and key guidance remains in
`commands.help.localized_copy`. The former
`interfaces.tui.operations.help` tree and the inverse `help_inventory` command
facade are intentionally absent.
The operation-neutral nested-session handoff remains directly implemented in
`memcommit.adapters.console.terminal.components.session_help`. The Help command
registers its inventory builder and selector as a backend after defining them;
the component therefore does not import a command module. Removing the former
inverse interface and shared facades keeps dependencies pointed in one
direction.

The historical `memcommit.help_application` and
`memcommit.help_lookup_application` paths remain behavior-free module-identity
aliases. They preserve existing imports, monkeypatch targets, and serialized
globals without creating parallel implementations. Importing
`memcommit.application.operations.help` alone remains lazy.

This relocation changes physical ownership only. It does not change catalog
copy, exact-name validation, natural-language prompt or result cardinality,
one-shot budget policy, provider routing, Study logging, or projection. The
terminal-only command handoff remains outside the application package and does
not broaden Help's Store or provider access.

| Route | Entry | Application path | Projection | Effect | Evidence |
| --- | --- | --- | --- | --- | --- |
| Plain `mem help` | `adapters.console.commands.help.command.cmd` in a non-TTY | `command_entries` takes `list_operation_help()` once | Plain alphabetized inventory plus CLI-owned forms, maturity tags, and canonical expanded details | None | `test_help_catalog.py`, `test_help_application.py` |
| Interactive `mem help` | Same command in a TTY | Flat operation snapshot plus `list_operation_help_groups()` | Grouped/A–Z browser; Search separates Retrieve & Answer from Synthesize, History separates Inspection from Recovery, and each divider is non-focusable; selected Form then shared exact-command argument editor | The editor closes before a separately recorded child command invocation; cancel has no effect | `test_help_catalog.py`, `test_help_command_handoff.py`, and the ordered Help captures |
| Natural-language `mem help REQUEST` | Same command with one positional request in TTY or non-TTY | `prepare_help_lookup` freezes and preflights the complete catalog before `connect_help_provider`; `execute_help_lookup` requires exactly three distinct exact IDs | Three existing collapsed Help rows in semantic order: `mem NAME`, summary, and `WHEN`; no ordinal, browser, why, confidence, forms, or generated prose | None | `test_help_lookup_application.py`, `test_help_lookup_cli.py`, `test_help_lookup_provider_policy.py` |
| Selected CLI detail | One `CommandEntry` from the snapshot | Catalog meaning already bound to the entry | Common meaning composed with registered CLI syntax | None | `test_help_catalog.py` |
| Python list | `MemCommitClient.list_operations()` | `_operations.help.list_operations` → `list_operation_help` | `HelpCatalogResult` of immutable DTOs, including compact typed-detail references | None | `test_help_public_api.py`, import-boundary tests |
| Python describe | `MemCommitClient.describe_operation(name)` | `_operations.help.describe_operation` → application exact lookup | One `OperationHelpResult` or `HelpInputError` | None | `test_help_public_api.py` |
| Python detail list/describe | `MemCommitClient.list_operation_details(name)` / `describe_operation_detail(name, id)` | Exact application detail lookup | Compact typed references or one complete comparison, limitation, access boundary, or semantic boundary | None | `test_help_public_api.py` |
| Agent list/describe/detail | `HelpAgentAdapter.invoke` | The corresponding public client method | Version-1 JSON-safe operation and individually addressable typed details; `effect: NONE` | None | `test_help_agent_adapter.py`, registry tests |
| Companion Skill | Installed Skill frontmatter and procedural body | Calls its registered agent tool; it does not execute Help | Frontmatter carries the trigger; the body may name a stable detail ID instead of copying its full payload | None until the selected tool is called | Add Skill contract and validator |

## Invariants

1. The flat application list is alphabetized, unique, immutable, and complete
   for all 66 visible public operations. The grouped application list preserves
   catalog family and section order. Every operation belongs to exactly one
   top-level catalog family; an optional section set must exactly partition its
   family without changing order. Compare belongs to Search's Synthesize
   section, while quality, impact, conformance, and saved-evidence
   operations remain under Check & Review.
2. Describe accepts one exact public operation name and detail lookup accepts
   one exact operation-local detail ID; neither performs fuzzy, alias, case, or
   whitespace normalization.
3. Stable summary, flow, execution, effect, range, use-when, maturity, and typed
   detail meaning originates in `operation_catalog`; adapters do not author
   substitute operation descriptions. Composite tools may own one reviewed
   composite use-when value. A Help maturity tag describes product scope and
   is not a route-classification state from the operation evidence ledger.
4. Every detail has a typed kind, stable operation-local ID, discovery role,
   and exact owner. `TOOL_SELECTION` requires a bounded one-line discovery
   summary; `ON_DEMAND` content is not injected into every tool description.
5. No generic notes bag or second prose registry exists. Full detail payloads
   are retrieved through the same application boundary by exact ID.
6. CLI forms, aliases, responsive layout, divider glyphs, and focus remain
   interface values. Family and section identity, ordered membership, and intent originate in the top-level
   operation catalog; version-1 Python and agent Help records do not yet expose
   the family or section fields.
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
11. Interactive CLI handoff fixes the selected `mem OPERATION` prefix, validates
    the edited arguments, and passes an argv sequence directly to a child
    process. It never evaluates a shell command string.

## Intentional exclusions

Framework-generated `mem <operation> --help` syntax remains a Typer/Click
projection over registered commands. Static registration reads the canonical
one-line summary, but parser rendering is not a parallel application use case.
Per-operation wording review remains separate. A Skill may name a stable detail
ID and retain the minimum procedural consequence needed to avoid an unsafe or
wrong tool call, but it is host guidance rather than another
operation-description source.

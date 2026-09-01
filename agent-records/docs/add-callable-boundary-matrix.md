# Add callable and effect boundary matrix

Last verified: 2026-09-01.

This matrix records ownership and effects for the first writable operation
exposed through several adapters. A callable's layer determines where it may be
reused; sharing a result type does not transfer authority or durable effects to
an interface.

| Callable | Owner | Input → output | Allowed effects | Required invariant | State |
| --- | --- | --- | --- | --- | --- |
| `operations.add.application.validate_add_request` | application | `AddRequest` → validated request | none | complete nonblank ordered batch before target access | `VERIFIED` |
| `operations.add.application.prepare_add_target` | application | locator + target port → frozen target | target identity/authority read only | one canonical name and Context UID | `VERIFIED` |
| `operations.add.application.run_add` | application | request + port → `AddResult` | effects delegated once to port | receipt covers every exact input in order and the frozen target | `VERIFIED` |
| `operations.add.runtime.MemoryStoreAddTargetPort.freeze` | infrastructure | locator → frozen target/token | Store/Profile/Grant reads | one current snapshot; optional local-only boundary; CREATE authority | `VERIFIED` |
| `operations.add.runtime.MemoryStoreAddTargetPort.append` | infrastructure | frozen target + request → result | one authorized Context save and Add checkpoint | target UID/digest and Grant revalidation; no overwrite | `VERIFIED` |
| `operations.add.runtime.execute_add` | infrastructure composition | request + Store → result | same Store effects as port | no terminal or provider dependency | `VERIFIED` |
| `commands.add.receipt.render_add_receipt` | Add console receipt | typed result + intake mode → terminal text | stdout only | no Store, authority, or mutation decisions | `VERIFIED` |
| `commands.add.workbench.build_add_workbench_setup` | Add workbench composition | Store + current snapshot + requested target → frozen setup | Store/Profile/Grant reads only | visible rows remain distinct from CREATE-selectable targets; no mutation | `VERIFIED` |
| `commands.add.workbench.run_add_workbench` | Add interactive workbench | frozen setup + application callback → result/cancel | process-local drafts and terminal I/O; callback only at To Do | cancellation and draft edits do not call application | `VERIFIED` |
| `commands.add.cmd` | console composition | argv/TTY → typed request and presentation | intake reads, TUI/CLI, application effects | `--to`, `--context`, and `-c` populate one scalar requested Target; the last occurrence wins and the receipt names the resolved Target; captures current once; file/paste parsing remains interface-owned | `VERIFIED` |
| `api.client.MemCommitClient.add_memories` | public Python facade | explicit text sequence + target → `AddMemoriesResult` | one application Add | explicit roots local-only; nonlocal Grant requires active Profile; stable errors | `VERIFIED` |
| `adapters.agent.add.AddAgentAdapter.invoke` | agent adapter | strict version-1 JSON object → JSON-safe receipt/error | exactly one public Add call after local validation | exact order/duplicates; complete receipt; no automatic mutation retry | `VERIFIED` |
| `adapters.agent.add.add_agent_tool_schema` | agent adapter | none → fresh function-tool schema | none | strict fields/version; duplicate Memory items remain legal | `VERIFIED` |
| default `AgentToolBinding` for Add | agent registry | standard Add schema + public Help trigger/detail references → frozen discovery definition | none | nonblank `use_when` and typed `copy-or-link` reference stay outside the standard function-tool schema; malformed binding fails at host construction | `VERIFIED` |
| `skills/memcommit-add/SKILL.md` | agent host guidance | user intent + discovered tool → bounded tool procedure | none by itself | frontmatter states when to use Add; literal content is not object lookup; independent work, Reference snapshot, and live Embed stay distinct | `VERIFIED` |

## Operation effect summary

| Entry route | Provider/cache/session | Durable success | Failure publication |
| --- | --- | --- | --- |
| CLI single, explicit batch, file, or paste | none | exact Memories and one Add checkpoint | none before completed Store save |
| Add TUI | process-local drafts only | exact reviewed drafts and one Add checkpoint | cancel/edit failure publishes nothing |
| Public Python | none | explicit ordered sequence and one Add checkpoint | typed error; no partial public receipt |
| Agent tool adapter | none | same public Add and JSON-safe complete receipt | bounded error; every failure is non-retryable |
| Companion Skill | none until tool invocation | no independent effect | missing tool is reported; no CLI/filesystem fallback |

The public method does not call the CLI and the application does not call the
public facade. CLI and TUI point to the application/runtime boundary; the
Python facade and agent projection point inward without importing either
terminal adapter. The Skill remains host guidance rather than an Add
implementation or callable; no wire transport is currently shipped.

The canonical implementation owner is `memcommit.application.operations.add`: its
`application` module owns the terminal-independent request, validation, port,
and receipt contracts, while its `runtime` module owns the Store and Grant
adapter. The historical `memcommit.add_application` and
`memcommit.add_runtime` paths are identity-preserving compatibility aliases,
so either import order, existing monkeypatches, and serialized globals resolve
to the same canonical module objects. Production adapters import the operation
package directly. This relocation changes no intake, authority, checkpoint,
CAS, output, or TUI behavior. Semantic result memorization is separately owned
by `application.capabilities.semantic_result_memorization`; generated-result
ADD effects do not make their originating operations part of exact Add.

## CLI Target spelling

Add has one receiving Context. `--to TARGET`, `--context TARGET`, and `-c TARGET`
are aliases for one scalar requested Target so the command adapter carries one
Python value rather than reconstructing one domain operand from separate CLI
variables. As with an ordinary scalar Click/Typer option, the last occurrence
wins when aliases are repeated or mixed. Every successful Add receipt names the
resolved Target, including the single-Memory route, so the published result
makes that final selection visible.

This role alias is deliberately asymmetric. Edit and Remove use
`--context`/`-c` to qualify the owner of an existing Memory; they do not accept
`--to`, which would misleadingly imply a destination, movement, or result
Context. No target authority, locator resolution, or Add materialization
behavior changes with the aliases; only CLI selection and single-Memory receipt
presentation differ.

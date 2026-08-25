# Add callable and effect boundary matrix

Last verified: 2026-08-25.

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
| `interfaces.cli.add.render_add_plain` | CLI adapter | typed result + intake mode → terminal text | stdout only | no Store, authority, or mutation decisions | `VERIFIED` |
| `interfaces.tui.operations.add.run_add_tui` | TUI adapter | frozen setup + application callback → result/cancel | process-local drafts and terminal I/O; callback only at To Do | cancellation and draft edits do not call application | `VERIFIED` |
| `commands.add.cmd` | console composition | argv/TTY → typed request and presentation | intake reads, TUI/CLI, application effects | `--to` is the preferred Target spelling; `--context`/`-c` remain compatible; duplicate spelling fails before Store access; captures current once; file/paste parsing remains interface-owned | `VERIFIED` |
| `api.client.MemCommitClient.add_memories` | public Python facade | explicit text sequence + target → `AddMemoriesResult` | one application Add | explicit roots local-only; nonlocal Grant requires active Profile; stable errors | `VERIFIED` |
| `interfaces.agent.add.AddAgentAdapter.invoke` | agent adapter | strict version-1 JSON object → JSON-safe receipt/error | exactly one public Add call after local validation | exact order/duplicates; complete receipt; no automatic mutation retry | `VERIFIED` |
| `interfaces.agent.add.add_agent_tool_schema` | agent adapter | none → fresh function-tool schema | none | strict fields/version; duplicate Memory items remain legal | `VERIFIED` |
| default `AgentToolBinding` for Add | agent registry | standard Add schema + public Help trigger/detail references → frozen discovery definition | none | nonblank `use_when` and typed `copy-or-link` reference stay outside the standard function-tool schema; malformed binding fails at host construction | `VERIFIED` |
| `McpRegistryProjection` for Add | MCP adapter | frozen discovery definition → MCP Tool | none during discovery; call delegates exactly once | standard description exposes the bounded selection summary; `memcommit/useWhen` and `memcommit/helpDetails` retain structured discovery; input schema remains unchanged | `VERIFIED` |
| `skills/memcommit-add/SKILL.md` | agent host guidance | user intent + discovered tool → bounded tool procedure | none by itself | frontmatter states when to use Add; literal content is not object lookup; independent work, Reference snapshot, and live Embed stay distinct | `VERIFIED` |

## Operation effect summary

| Entry route | Provider/cache/session | Durable success | Failure publication |
| --- | --- | --- | --- |
| CLI single, explicit batch, file, or paste | none | exact Memories and one Add checkpoint | none before completed Store save |
| Add TUI | process-local drafts only | exact reviewed drafts and one Add checkpoint | cancel/edit failure publishes nothing |
| Public Python | none | explicit ordered sequence and one Add checkpoint | typed error; no partial public receipt |
| Agent tool adapter | none | same public Add and JSON-safe complete receipt | bounded error; every failure is non-retryable |
| MCP-projected agent tool | none during discovery | same agent/public Add after a call | same bounded envelope; transport does not reinterpret retry or success |
| Companion Skill | none until tool invocation | no independent effect | missing tool is reported; no CLI/filesystem fallback |

The public method does not call the CLI and the application does not call the
public facade. CLI and TUI point to the application/runtime boundary; the
Python facade and agent projection point inward without importing either
terminal adapter. MCP remains a projection of the frozen agent registry, and
the Skill remains host guidance rather than an Add implementation or callable.

The canonical implementation owner is `memcommit.operations.add`: its
`application` module owns the terminal-independent request, validation, port,
and receipt contracts, while its `runtime` module owns the Store and Grant
adapter. The historical `memcommit.add_application` and
`memcommit.add_runtime` paths are identity-preserving compatibility aliases,
so either import order, existing monkeypatches, and serialized globals resolve
to the same canonical module objects. Production adapters import the operation
package directly. This relocation changes no intake, authority, checkpoint,
CAS, output, or TUI behavior and does not absorb the separate semantic Add
materialization helpers used by generative operations.

## CLI Target spelling

Add has one receiving Context, so `--to TARGET` names the operand by its role
and is the preferred explicit spelling. The established `--context TARGET` and
`-c TARGET` forms remain compatible because they already identify the same
CREATE-authorized destination. Supplying `--to` together with either
compatibility spelling fails before Store construction; argument order must not
silently retarget a mutation.

This role alias is deliberately asymmetric. Edit and Remove use
`--context`/`-c` to qualify the owner of an existing Memory; they do not accept
`--to`, which would misleadingly imply a destination, movement, or result
Context. No target authority, locator resolution, receipt, or Add materialization
behavior changes with the new spelling.

# Status application boundary matrix

## Closure statement

Every currently implemented Status route enters one terminal-independent
application/runtime boundary. The operation freezes one current readable
Context scope, returns typed inventory, bounded preview, relationship, and
checkpoint facts, and performs no provider or mutation lifecycle.

| Route | Entry | Application path | Projection | Effect | Evidence |
| --- | --- | --- | --- | --- | --- |
| Detailed direct | `mem status`, `mem status -d` | `execute_status` → `MemoryStoreStatusSource.freeze` → `inspect_status` | Inventory, conditional relationships, first-five Memory preview, latest-five checkpoints | None | application and CLI tests |
| Detailed recursive | `mem status -r` | same boundary with lexical and embed reach enabled | Current detail plus aggregate and per-Context direct counts | None | recursive namespace/embed tests |
| Compact direct | `mem status -s` | same typed result | One current Context count row | None | short-output tests |
| Compact recursive | `mem status -sr` | same typed result | One direct-count row per Context | None | short recursive tests |
| Profile lineage | `mem status -b`, `mem status -sb` | same typed result plus frozen Profile identity | Profile and Context lineage | None | branch-style orientation tests |
| READ-granted current | any current Status form | exact READ resolution under one registry generation | Public name, permissions, read-only state; no authority checkpoints | None | authority-grant regressions |
| Attached Grants | detailed owned current Context | Profile-backed attachment snapshot | Conditional Grant relationship rows without opening authority content | None | attached-Grant regression |
| Query-only view | detailed current Context | opaque query-row projection | Relationship metadata only | None | query-only concealment regression |

## Callable matrix

| Callable | Current owner | Intended layer | Inputs/result | Effects | Authority/cache boundary | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `inspect_status` | `memcommit.status_application` | Application | `StatusRequest` + `StatusSourcePort` → `StatusResult` | Through injected read port only | Owns bounded preview/history policy; no cache/session/receipt | direct application tests |
| `MemoryStoreStatusSource.freeze` | `memcommit.status_runtime` | Infrastructure adapter | typed reach → `FrozenStatusFrame` | Store/Profile/Grant/checkpoint reads | Resolves READ before content projection; one registry generation | runtime, recursive, Grant tests |
| `execute_status` | `memcommit.status_runtime` | Composition | request + explicit Store → typed result | Same read effects as source port | No terminal import or output | runtime no-output test |
| `render_status` | `memcommit.interfaces.cli.status` | CLI presenter | typed result + display flags → text | stdout only | Cannot load Store, resolve authority, or change scope | CLI output tests |
| `commands.status.cmd` | Typer adapter | CLI parsing/error boundary | flags → request and presenter | Store construction and terminal error reporting | Delegates all substantive read policy | command regressions |

## Invariants

1. Current Context orientation is read exactly once inside the frozen Profile
   and Grant snapshot.
2. The current Context is the first result row. Every additional Context is
   readable under the same catalog generation and unique by durable UID.
3. The preview contains only the first five ordinary direct Memories in
   persisted order. It excludes references, query views, embeds, Grants, and
   descendant bodies.
4. Recent changes contain at most the five newest checkpoint summaries.
   Authority checkpoints are never exposed through a granted view.
5. Status never dereferences a Memory reference and never opens concealed
   query-only source content.
6. Recursive reach expands canonical lexical descendants and follows explicit
   embed edges independently. Grant attachment is authorization metadata, not
   a hierarchy edge.
7. No successful or failed Status call writes a Context, checkpoint, cache,
   receipt, session, Profile pointer, or current Context pointer.

## Deliberate non-goals

Status is not an exact diff, full history browser, content listing, or complete
Memory reader. Those remain `diff`, `log`, `list`, and `show`. There is no
interactive Status TUI or public Python/agent/MCP adapter in the current route
set; adding one must project this typed result rather than reimplementing the
read policy.

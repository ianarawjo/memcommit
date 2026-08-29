# Switch application boundary

Last reviewed: 2026-08-28.

## Purpose

`mem switch` changes only the active Profile Store's current-Context pointer,
but the former command module also owned lexical locator resolution, READ
authorization, target loading, Grant revalidation, target/current
compare-and-swap, terminal selection, and output.  That made the shared
Context picker discoverable only through a command adapter and left Ground's
process-local `P` picker importing another command's implementation.

This slice separates three contracts without changing their meaning:

1. `operations/switch/application.py` owns one typed current-pointer transition;
2. `operations/switch/runtime.py` supplies Store and Grant infrastructure; and
3. the command-owned setup and receipt adapters parse, select, and render
   without reconstructing locator, authority, or CAS policy.

The former top-level application and runtime paths remain module-identity
aliases. This ownership-only relocation changes no request, result, error,
authorization, Store effect, command output, or TUI interaction contract.

It does not add a Python or agent API, a current-Ground pointer, fuzzy Context
search, a checkpoint, or Undo/Redo support.

The later navigation-history extension adds typed `PREVIOUS` and `NEXT` CLI
routes without changing picker interaction. Its optional bounded state schema,
actual-visit ordering, concurrency rules, and rejected lexical-order shortcut
are recorded in
[`mem-switch-navigation-history-design-rationale.md`](mem-switch-navigation-history-design-rationale.md).

## Call paths

```text
mem switch NAME
  -> SwitchContextRequest(selector, command-start current)
  -> switch_context()
  -> MemoryStoreSwitchContextPort
  -> READ resolution + target load + current/target CAS
  -> SwitchContextResult
  -> plain CLI presenter

mem switch --previous | --next
  -> typed history direction + command-start current
  -> saved target resolution
  -> the same READ resolution + target load
  -> current/history CAS
  -> SwitchContextResult

mem switch
  -> frozen local/Grant navigation catalog
  -> commands/switch/setup.py
  -> terminal.components.context_picker
  -> selected name only
  -> the same SwitchContextRequest and application/runtime path

Ground P
  -> terminal.components.context_picker
  -> process-local NOT BOUND name only
  -> no Switch application call and no state.json write
```

`mem checkout` without `-b` continues to dispatch to `commands.switch.cmd` and
therefore enters the same application path. `checkout -b` remains the separate
Branch operation.

The console-specific input and output adapters are co-located under
`memcommit.adapters.console.commands.switch`: `command.py` owns orchestration,
`setup.py` translates one shared-picker selection into a typed request, and
`receipt.py` owns successful human-readable output. The former operation-specific
TUI and CLI interface paths are removed without facades. The shared Context
picker is owned by `adapters.console.terminal.components.context_picker`, while
the tree, reach, selection, and typed targets remain in core Context targeting.
This ownership split does not change interaction, authority, or the
current-pointer contract.

## Responsibility matrix

| Concern | Owner after extraction | Contract |
| --- | --- | --- |
| Typer grammar, cancellation, and error presentation | `commands/switch/command.py` | Captures current once, routes an optional TUI selection, invokes the typed use case, and renders the result. |
| Interactive Switch shape | `commands/switch/setup.py` | Converts one frozen picker result into `SwitchContextRequest`; it performs no load, authorization, or write. |
| Shared Context tree, direct-item preview, focus, and clipboard | Core `context_targeting/tui/tree.py` plus terminal `components/context_picker` | Core owns the frozen tree and typed targeting state; the terminal component projects and returns a Context name or read-only targeting value without owning an operational role or Store continuation. |
| Legacy picker imports | `commands/shared/context_picker.py` | Behavior-free compatibility exports only; production callers use the neutral owner directly. |
| Global versus explicit-relative name semantics | `operations/switch/application.py` | Bare names remain canonical global names. Only `.`, `..`, `./...`, and `../...` resolve against the command-start current snapshot. |
| Previous/next navigation meaning | `current_context_navigation.py` + `operations/switch/application.py` | Uses bounded actual pointer-transition history, never lexical catalog adjacency; direct selection clears forward history. |
| Exact lexical-parent requirement | `operations/switch/application.py` through `SwitchContextPort.local_context_exists` | A missing lexical parent is never inferred from an Embed edge. |
| Local/Grant READ resolution and target loading | `operations/switch/runtime.py` | A visible public name is selectable only when its exact route authorizes ordinary READ. QUERY-only rows remain orientation-only. |
| Local target/current CAS | `MemoryStore.set_current_context_if` | Binds the target UID/digest and the command-start current pointer. |
| Granted current publication | `authority_grant_snapshot_lock` plus `set_current_virtual_context_if` | Reauthorizes the exact public route under the registry lock before writing the virtual pointer. |
| Success rendering | `commands/switch/receipt.py` | Preserves `Switched to context ...` and `Already on ...` output. |

## Operation contract matrix

| Axis | Switch classification | Evidence or intentional boundary |
| --- | --- | --- |
| `APP-01` application entry | `VERIFIED` for current routes | Explicit CLI, interactive Switch, and checkout compatibility all enter `SwitchContextRequest` and `execute_switch_context`. |
| `APP-02` locator/targeting | `VERIFIED` for Switch | One current snapshot, explicit relative grammar, canonical target identity, and the shared picker are tested. |
| `APP-03` authority/freshness | `VERIFIED` for Switch | READ is required; local target UID/digest and current pointer are CAS-bound; granted routes reauthorize under the registry lock. |
| `IMPORT-01` assembly | `CHARACTERIZED` | Operation-owned application/runtime modules import no Typer, prompt-toolkit, command, or unrelated operation adapters. Top-level compatibility paths alias the same module objects, and the operation package adds no eager export. |
| `SEM-01` provider | `N/A` | Switch is deterministic and never constructs or calls a semantic provider. |
| `CACHE-01` prepared reuse | `N/A` | There is no semantic result to cache or project. |
| `SESSION-01` saved analysis | `N/A` | Picker state is process-local; Switch creates no saved analysis/session. |
| `APPLY-01` reviewed proposal | `N/A` | An explicit command or Enter-selected target is the direct navigation request, not a staged semantic proposal. |
| `EFFECT-01` checkpoint/Undo | intentional exclusion | Only the process-global current pointer changes. Contexts and checkpoints are unchanged, and navigation is not part of Context Undo/Redo. |
| `TUI-02` interaction | `CHARACTERIZED` | Shared tree/focus/preview/clipboard behavior remains covered by the Switch picker suite. |
| `TUI-C04` Context targeting | `CHARACTERIZED` | Core owns operation-neutral tree/reach/target values; the complete prompt-toolkit picker has the terminal component owner. |
| `TUI-A01` operation adapter | `CHARACTERIZED` | `commands/switch/setup.py` owns the Switch label/default/result-to-request translation only. |
| `HELP-01` discovery | unchanged | Existing command forms and help wording remain authoritative. |

## Ground boundary

Ground automatic Context recommendation is deliberately not a Switch service.
Before a Ground is named, `ground_context_catalog.py` scans regular
`contexts/**/context.json` locator paths without opening their JSON records.
It sends at most 64 alias/name pairs to the provider and keeps current,
discovered, recommended, selected, new, and bound states distinct.  Replacing
that scanner with Switch's ordinary catalog would violate the content-free
startup boundary because the ordinary catalog may validate record headers.

Only the already-frozen name tree is shared.  Ground's `P` action calls the
neutral picker directly, records the returned name as process-local
`NOT BOUND`, and never invokes `switch_context`.  A focused integration test
proves that the action does not create `state.json` or alter its bytes.

## Durable and safety invariants

1. The current name is captured once before optional terminal interaction.
2. A bare name is global; only explicit relative syntax depends on current.
3. A picker result is reauthorized and reloaded after the picker closes.
4. Local publication binds the loaded target UID/digest and current snapshot.
5. Granted publication reauthorizes under the registry lock; visibility alone
   never becomes READ authority.
6. Cancellation, malformed locators, missing/unloadable targets, revoked
   Grants, target races, and current-pointer races leave no partial Switch
   success.
7. Switch never mutates a Context, checkpoint, Ground, cache, or session.
8. Ground direct selection remains process-local and cannot become an implicit
   Switch or binding continuation.
9. Previous/next publication consumes only the exact command-time direction
   target after normal READ validation; failure leaves both pointer and stacks
   unchanged.

## Verification gate

The focused verification set covers the typed application contract, complete
legacy Switch picker/CLI behavior, relative names, query-only rejection,
READ-granted public names, concurrent current/target changes, checkout
compatibility, shared picker rendering and clipboard behavior, import
direction, and Ground's process-local direct-selection path.  The repository
architecture test continues to reject every `interfaces` to `commands`
import, while the Switch-specific test rejects any behavior definition in the
legacy picker facade or production import through that path.

The ordered `180x52` color-PTY record under
`agent-records/docs/screenshots/switch-application-boundary-20260816/` covers picker entry,
navigation, cancellation, successful selection, the typed success receipt,
and read-only current-pointer verification.  The accompanying Ground record
covers its `P` handoff and confirms `NOT BOUND` without a state write.

## Remaining boundaries

- Switch remains an internal console slice. A stable Python or agent contract
  would need separately versioned errors and an explicit decision about
  exposing process-global navigation state to concurrent hosts.
- The Typer registry is still the eager console composition root.
- Context catalog reads and current-state reads are not one atomic snapshot;
  post-picker authorization, target loading, and final CAS remain the safety
  boundary.
- The shared picker is one coherent module but still large. Future splitting
  should follow stable subcontracts such as preview, clipboard, rendering, and
  screen composition rather than visual file-size targets.

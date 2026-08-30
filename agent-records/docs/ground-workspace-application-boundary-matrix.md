# Ground workspace application boundary matrix

## Status

Physical creation/loading/editing, terminal routing, local-history isolation,
shared Goal operands, Distill/Makemore adoption, and
Distill/Makemore/Fit/Conformance consumers are implemented and tested. The
legacy session Store and model are removed. Authority-aware typed-reference
projection and a writable conversational TUI remain migration gates.

| Concern | Application/domain owner | Infrastructure owner | Interface owner | Current evidence | Remaining gate |
| --- | --- | --- | --- | --- | --- |
| Workspace shape | `ground_workspace.py` | none | none | Exact root plus `goals`, `rules`, `examples`, `contexts`, and `relations`; distinct UIDs | Keep every later consumer on the same aggregate |
| Require-new creation | `ground_workspace_application.py` | `ground_workspace_runtime.py` + atomic `MemoryStore.create_missing_contexts` | exact blank-shell approval and named CLI | Complete rollback, one initial checkpoint per Context, no current switch | Keep future TUI creation on the same typed use case |
| Manifest | `GroundWorkspaceManifest` as one ordinary Memory | ordinary Context serialization | CLI/TUI read projection | Exact schema/kind/root UID/revision/status decoder; every local edit and Undo advances revision | Add status-changing reviewed actions only when their semantics are defined |
| Goal material | ordinary `Memory` in `/goals`; shared focus is only an exact projection | ordinary Context Store plus Goal operand freshness | `--goal`, `--set-goal`; read-only TUI | Context/Memory/text input, provenance receipt, 40-word validation, Distill/Makemore/Fit/Update focus consumption | Add inline TUI review over the same request types |
| Rules, Examples, relations | ordinary `Memory` in their physical lanes | ordinary Context Store | exact add flags; read-only TUI | Add, CAS, revision, local Undo; Rules/Examples feed semantic adapters | Add future reviewed actions only over ordinary Memories |
| External Context material | existing Context item types in `/contexts` | ordinary/granted Store loaders | existing Branch/Reference/Embed interfaces outside Ground | MemoryRef round trip; lexical descendant navigation/Distill/Fit | Add authority-aware typed-reference disclosure; current semantic projection fails closed before provider |
| Naming and discovery | real canonical Context names; root manifest marker | local Context catalog | shared operation launcher and Context targeting TUI | Namespaced roots, physical workspace catalog/open, local descendant rows, no global Switch | Keep discovery on the physical catalog; no parallel saved-session catalog |
| Freshness | touched Context CAS; operation-local semantic input freeze | Store CAS, Fit receipt Store, semantic pre/post revalidation | no interface-owned digest | Distill exact Goal/Examples/Contexts; direction-specific Makemore; Fit Goal/Rules/Examples/Contexts; unconsumed relation changes do not stale Fit | Install hidden Distill/Makemore receipts before claiming cache reuse |
| Ground-local Undo | root-scoped command-unit contract | checkpoint history and scoped restore | `mem ground NAME --undo` | Local/global stack isolation, LIFO edit units, drift rejection, monotonic revision, genesis exclusion | Add a TUI key only as an adapter to this use case; redo remains undesigned |
| Semantic adoption | complete Distill/Makemore proposal into one typed lane | root-plus-lane CAS batch with frozen non-target Source bindings | explicit line-oriented `--adopt` | all-or-none Rules/Examples, one revision, analysis digest, stale rejection, one local Undo unit | Add a reviewed TUI action only as an adapter |
| Retired Ground JSON | no application owner | no Store path, lock, reader, writer, or rename hook | no CLI or TUI route | source/test scan plus physical consumer regressions | Historical records are evidence only, not a compatibility contract |
| Component reuse | operation-owned workspace projection | none | `context_targeting.tui`, shared focus/frame/scrollable-pane, Ground adapter | Shared dependency direction, no Switch import, nonmutating TUI navigation tests, ordered 180×52 PTY evidence | Reuse the same components if writable panes are added; do not create a second workspace navigator |

## Cross-operation contract links

- `APP-01`: creation/loading are typed and terminal-independent.
- `IMPORT-01`: application/domain modules import no command, interface, Store,
  or prompt-toolkit owner.
- `APP-02`: real lexical subtree names use shared Context targeting; embedded
  traversal remains a separate axis.
- `APP-03`: typed external links retain their own authority and revalidation.
- `SEM-01`: semantic callers freeze only the material they consume.
- `SESSION-01`: the Context-rooted aggregate replaces the parallel session
  repository.
- `APPLY-01`: genesis creation is exact and separately approved; later edits
  consume exact physical state.
- `EFFECT-01`: Ground-local multi-Context command units do not enter the global
  Undo stack.
- `TUI-02`, `TUI-C04`, and `TUI-A01`: shared navigation mechanics and
  operation-owned selection meaning remain separate.

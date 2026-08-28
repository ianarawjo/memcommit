# Find callable boundary matrix

Last reviewed: 2026-08-25.

## Purpose

`Find` is the provider-free counterpart to semantic `Search`. It locates every
literal or explicitly requested regular-expression occurrence in one frozen
readable Context scope. The operation must be equally callable from CLI, TUI,
Python and agent routes without any route constructing a provider,
semantic cache, visible session, or mutation plan.

## Call path

```text
mem find PATTERN -------------------\
interactive Find workbench ----------+--> FindRequest
MemCommitClient.find ----------------+
agent memcommit_find ----------------/          |
                                                  v
                                      run_find
                                      (application)
                                                  |
                                  FindSourcePort
                                                  |
                             ReadableFindSourcePort
                                      (runtime adapter)
                                                  |
                                      FindResult
                                      /             \
                              plain presenter    TUI Viewer
```

## Package ownership

The canonical provider-free implementation now lives under
`memcommit.application.operations.find`. `application.py` owns the exact request,
frozen Source frame, span and result contracts, pattern validation, and
complete non-overlapping matching. `runtime.py` owns readable catalog
composition, lexical and embedded reach, MemoryRef resolution, and the Store
adapter that freezes the authorized corpus before matching. CLI, TUI, Python,
agent and presentation adapters import those operation-owned modules
directly.

The human console vertical is co-located under
`memcommit.adapters.console.commands.find`: `command.py` owns orchestration,
`presentation.py` and `source_row.py` own plain result projection, `compact.py`
owns completed-result paging, and `workbench/` owns interactive request setup
and result inspection. The former CLI and operation-specific TUI interface
paths are removed without facades. This changes ownership and canonical names
only; it does not change matching, scope, clipboard, paging, or terminal
interaction behavior.

The historical `memcommit.literal_find_application` and
`memcommit.literal_find_runtime` paths remain behavior-free module-identity
aliases. Old imports, monkeypatch targets, and serialized globals therefore
resolve to the same canonical module, while importing
`memcommit.application.operations.find` alone remains lazy.

This relocation names the implementation owner without changing public Find
semantics. It does not absorb semantic Search's `memcommit.find_application`
or `memcommit.find_runtime`, construct a provider, create a session, initiate
Replace, or change readable authority, traversal, matching, counts, spans,
presentation, or effect boundaries. Those separations are intentional
non-goals of the ownership-only move.

## Boundary matrix

| Boundary | Owner | Invariant |
| --- | --- | --- |
| Request | `FindRequest` | Nonempty pattern of at most 2,000 characters, at least one distinct public Context name, explicit lexical/embedded reach, case policy, and `LITERAL` or `REGEX` mode |
| Readable namespace | CLI/public composition adapters | Existing relative locators resolve against one captured current Context; Profile TUI breadth freezes `ReadableContextCatalog`; QUERY-only routes never become ordinary sources |
| Frozen source | `ReadableFindSourcePort` | Complete readable roots are loaded before matching; lexical descendants and embedded traversal remain independent; following embeds resolves an exact local Context's displayed attached READ rows through their frozen Grant bindings without opening QUERY-only content; graph cycles are deduplicated by Context UID; each searchable Memory-shaped item receives one contiguous frozen-corpus position before matching |
| Match semantics | `run_find` | Literal is default; regex is opt-in; zero-width regex is rejected; every non-overlapping span is retained with exact start/end/text |
| MemoryRef | runtime source collector | The selected owner and referenced Source identity are both retained; unresolved or unreadable references are skipped rather than opened through concealed authority |
| Result | `FindResult` | Complete scanned-item, matched-item, and occurrence counts accompany immutable per-item spans |
| Durable effect | none | No provider, cache, session, checkpoint, Context write, current switch, or materialization occurs |
| Presentation | command-owned plain and interactive adapters, neutral Source Reference projection, shared compact Scope, and shared compact pager mechanics | Rows use `N [UID] content, [Context mX]`, where `N` is match order and `mX` is frozen searchable-corpus position; Up to ten matches print inline; a longer supplied-pattern TTY result uses a primary-screen ten-row pager with `SHOWING a–b OF total`, row/page/boundary arrow navigation, wrapped complete rows, and a non-erasing close; `--plain` retains the bounded static projection and `--all-results` prints every row; `-a/--all` instead freezes every readable Context as the exact target set; Find never content-elides a Source row; operand-free `mem find` or explicit `--tui` opens a primary-screen `SCOPE → FIND → RESULTS` form whose direct exact Context input expands to Profile/multiple tree selection only while Browse is open; `y` copies the complete numbered focused row there, while `--copy` and TUI `Y` copy the complete typed result projection |
| Public adapters | Python and version-1 agent | Both call the same runtime/application boundary and return typed/JSON projections with `effect: NONE` and `provider_used: false` |

The shared compact selector projects descendant choices into the exact visible
checked set before request construction. This deliberately prevents an
independently unchecked child from being reintroduced by a second hidden
loader expansion.

## Verification

- `tests/test_find_application.py` checks literal, regex, case, span,
  complete-coverage, and zero-width rejection semantics without Store or UI.
- `tests/test_find_runtime.py` checks readable roots, independent
  lexical/embedded reach, MemoryRef provenance, cycles, and unavailable refs.
- `tests/test_granted_embed.py` checks that List, Show, Find, and semantic
  Search agree on an attached READ projection, preserve direct-scope
  exclusion, reject unsafe mixed recursive copy, and never disclose a nested
  QUERY-only Memory.
- `tests/test_find_cli.py` checks actual Typer routes, repeated roots,
  descendants, literal defaults, regex rejection, non-TTY behavior, short
  inline TTY output, long-result compact-pager routing, bounded `--plain`
  versus `--all-results`, complete clipboard output, and the explicit `--tui`
  override.
- `tests/test_paged_result.py` checks the operation-neutral range/total state,
  stable discrete pages, retained row position, result boundaries, and actual
  prompt-toolkit arrow dispatch without an operation model.
- `tests/test_find_presentation.py` checks shared logical-row grammar,
  complete unelided content, hidden human-facing spans, explicit page
  disclosure, distinct empty-scope output, and MemoryRef owner-to-Source
  provenance.
- `tests/test_find_tui.py` checks explicit execution, cancellation,
  visible descendant projection, and focused/whole clipboard contracts.
- `tests/test_find_public_api.py` and
  `tests/test_find_agent_adapter.py` check the public Python and
  versioned machine contracts, including provider/cache isolation.
- Registry tests prove the agent tool is exposed through
  the ordinary in-process registry rather than a CLI subprocess.

## Boundaries and non-goals

- Find does not rank by meaning, answer a question, save results, or initiate
  Replace. Those are separate reviewed operations.
- Matching is non-overlapping. Overlapping regex enumeration would require a
  different span and Replace cardinality contract.
- Compact rows do not remove spans from `FindResult`, public Python,
  agent projections, or Replace planning. They only omit raw offsets from
  the default human projection.
- Compact paging is presentation-only. It receives one frozen complete result,
  does not search again, and cannot broaden scope, change counts, or publish a
  partial application result.
- Readable MemoryRef text may be reported, but a later Replace cannot mutate
  the referenced Source through that Target pointer.

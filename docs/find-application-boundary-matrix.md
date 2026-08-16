# Find callable boundary matrix

Last reviewed: 2026-08-16.

## Purpose

`Find` is the provider-free counterpart to semantic `Search`. It locates every
literal or explicitly requested regular-expression occurrence in one frozen
readable Context scope. The operation must be equally callable from CLI, TUI,
Python, agent, and MCP routes without any route constructing a provider,
semantic cache, visible session, or mutation plan.

## Call path

```text
mem find PATTERN -------------------\
interactive Find workbench ----------+--> LiteralFindRequest
MemCommitClient.find ----------------+
agent/MCP memcommit_find ------------/          |
                                                  v
                                      run_literal_find
                                      (application)
                                                  |
                                  LiteralFindSourcePort
                                                  |
                             ReadableLiteralFindSourcePort
                                      (runtime adapter)
                                                  |
                                      LiteralFindResult
                                      /             \
                              plain presenter    TUI Viewer
```

## Boundary matrix

| Boundary | Owner | Invariant |
| --- | --- | --- |
| Request | `LiteralFindRequest` | Nonempty pattern of at most 2,000 characters, at least one distinct public Context name, explicit lexical/embedded reach, case policy, and `LITERAL` or `REGEX` mode |
| Readable namespace | CLI/public composition adapters | Existing relative locators resolve against one captured current Context; Profile TUI breadth freezes `ReadableContextCatalog`; QUERY-only routes never become ordinary sources |
| Frozen source | `ReadableLiteralFindSourcePort` | Complete readable roots are loaded before matching; lexical descendants and embedded traversal remain independent; graph cycles are deduplicated by Context UID |
| Match semantics | `run_literal_find` | Literal is default; regex is opt-in; zero-width regex is rejected; every non-overlapping span is retained with exact start/end/text |
| MemoryRef | runtime source collector | The selected owner and referenced Source identity are both retained; unresolved or unreadable references are skipped rather than opened through concealed authority |
| Result | `LiteralFindResult` | Complete scanned-item, matched-item, and occurrence counts accompany immutable per-item spans |
| Durable effect | none | No provider, cache, session, checkpoint, Context write, current switch, or materialization occurs |
| Presentation | independent CLI/TUI adapters | Memory text uses shared Memory styling; `y` copies one focused match and `Y` copies the complete typed result |
| Public adapters | Python and version-1 agent/MCP | Both call the same runtime/application boundary and return typed/JSON projections with `effect: NONE` and `provider_used: false` |

The interactive selector projects descendant choices into the exact visible
checked set before request construction. This deliberately prevents an
independently unchecked child from being reintroduced by a second hidden
loader expansion.

## Verification

- `tests/test_literal_find_application.py` checks literal, regex, case, span,
  complete-coverage, and zero-width rejection semantics without Store or UI.
- `tests/test_literal_find_runtime.py` checks readable roots, independent
  lexical/embedded reach, MemoryRef provenance, cycles, and unavailable refs.
- `tests/test_literal_find_cli.py` checks actual Typer routes, repeated roots,
  descendants, literal defaults, regex rejection, and non-TTY behavior.
- `tests/test_literal_find_tui.py` checks explicit execution, cancellation,
  visible descendant projection, and focused/whole clipboard contracts.
- `tests/test_literal_find_public_api.py` and
  `tests/test_literal_find_agent_adapter.py` check the public Python and
  versioned machine contracts, including provider/cache isolation.
- Registry and MCP projection tests prove the agent tool is exposed through
  the ordinary in-process registry rather than a CLI subprocess.

## Boundaries and non-goals

- Find does not rank by meaning, answer a question, save results, or initiate
  Replace. Those are separate reviewed operations.
- Matching is non-overlapping. Overlapping regex enumeration would require a
  different span and Replace cardinality contract.
- Readable MemoryRef text may be reported, but a later Replace cannot mutate
  the referenced Source through that Target pointer.

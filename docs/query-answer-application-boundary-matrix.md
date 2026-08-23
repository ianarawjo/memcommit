# Ordinary Query answer application-boundary matrix

Last verified: 2026-08-20.

## Decision

Ordinary Query's read-only answer is an application use case, not a CLI or TUI
method. `memcommit.operations.query.ordinary_application` owns the exact
request, frozen-source contract, provider-ordering invariant, typed response,
and reference-document assembly.
`memcommit.operations.query.ordinary_runtime` adapts `MemoryStore` and a frozen
readable Context catalog to that use case. Console and workbench code only
resolve controls, select a provider factory, project progress, and present the
result.

This slice deliberately excludes authority QUERY routes and legacy
`QueryContextRef`. Granted QUERY's distinct provider-before-concealed-Source
read contract is recorded in
`granted-query-read-publication-design-rationale.md`; they do not broaden this
ordinary read-only contract.

## Execution shape

```text
CLI question --------------------\
                                  -> OrdinaryQueryRequest
interactive Query workbench -----/          |
                                             v
                                  run_ordinary_query
                                             |
                              OrdinaryQuerySourcePort.freeze
                                             |
                         MemoryStoreOrdinaryQuerySourcePort
                                             |
                       complete frozen candidate frame + label
                                             |
                              whole-frame semantic preflight
                                             |
                               configured provider factory
                                             |
                       answer blocks + locally validated aliases
                                             |
                    host-numbered OrdinaryQueryResponse references
```

## Responsibility matrix

| Boundary | Owner | Frozen before provider use | Invariant |
| --- | --- | --- | --- |
| Request | `OrdinaryQueryRequest` | Nonblank question, distinct canonical readable names, explicit lexical and embedded reach | The adapter cannot change scope after execution starts |
| Read authority | Caller plus frozen readable catalog | Exact `ContextAccess` for every reachable public name | READ is resolved before the runtime can open candidate content |
| Source frame | `MemoryStoreOrdinaryQuerySourcePort` | Complete roots and search candidates for the exact request | READ-granted Memories may contribute; Profile-local artifacts never cross a Grant |
| Empty frame | Application | Label and empty candidate tuple | Returns the established no-grounded-answer result without constructing a provider |
| Semantic preflight | `prepare_ordinary_query_answer` | Complete evidence frame, prompt budget, output schema | Over-budget whole-frame work fails before provider construction; no ranking, truncation, or hidden batching |
| Provider | Injected `OrdinaryQueryProviderFactory` | Constructed only after freeze and preflight | Exactly one completion sees every frozen candidate once |
| Answer | `complete_ordinary_query_answer` | Strict answer blocks or one explicit no-answer explanation | Provider cannot forge numeric citations, unknown aliases, or unsourced answer blocks |
| References | Application plus neutral Source Reference projection | Host-compacted authorized evidence | Host assigns citation numbers and Query aliases, then maps each used Source to the shared `[N] content — UID prefix, Context, alias` row; the shared renderer never selects evidence or assigns either identity |
| Result | `OrdinaryQueryResponse` | Exact request, nonblank answer, grounded flag, optional matching reference document | Ungrounded results cannot expose evidence references |
| Durable effect | None | None | No Context, current pointer, checkpoint, session, transcript, or cache receipt is written |

## Observable parity

The extraction preserves the existing ordinary Query contract:

- default request values remain `include_descendants=False` and
  `follow_embeds=True`;
- the same readable search-root and candidate collectors freeze the corpus;
- a single selected target uses its public name as the empty/no-answer label;
- multiple targets use `<n> selected Contexts`;
- CLI `-a/--all` expands the frozen Profile-readable catalog to concrete exact
  target names and authorizes their combined semantic use before provider
  construction;
- empty frames still render `(no grounded answer found)`;
- grounded and no-answer strings retain their prior formatting;
- the same whole-frame prompt, schema, decoder, artifact compaction, citation
  numbering, and Reference document are used;
- every compact Reference remains self-contained when adjacent citations come
  from different Contexts; stored line breaks are folded and no blank row is
  inserted between citations;
- Query's typed citation object and literal Find's typed match remain separate;
  only their final Source row model and punctuation are shared;
- the CLI, TUI, tests, and capture tools call the operation runtime directly;
  and
- the Typer composition root retains the same two visible progress labels
  while the application observer exposes typed stages.

No visible TUI state, focus topology, key binding, output wording, provider
policy, or scope default is changed by this slice. Concurrent scope-preset and
clipboard work remains outside this commit.

## Verification

`tests/test_query_application.py` proves:

- source freezing precedes provider construction;
- a nonempty complete frame produces one typed grounded answer and Reference;
- an empty frame is provider-free;
- whole-frame preflight failure is provider-free;
- invalid question, target cardinality, and scope values fail at request
  construction;
- exact direct scope excludes a lexical child;
- execution emits no terminal output and preserves every Source Context; and
- application/runtime modules import no command, Typer, prompt-toolkit, or
  concrete provider module, while only the runtime imports `MemoryStore`.

The focused application, synthesis, provider, and workbench suite passed after
the extraction. The existing compatibility test
also verifies that its progress projection remains exactly `connecting
provider` followed by `answering from complete frozen corpus`.

An expanded Query-related run passed 105 tests, and a wider Query/Find/authority
run passed 211 tests before one unrelated existing Embed interface-import
failure. The exact isolated commit tree passed Ruff, both application/runtime
module type checks, and 50 application, synthesis, provider-policy, provider,
and workbench tests. CLI-importing tests in that isolated tree remain gated by
the pre-existing committed Summarize import of `declared_artifact_available`,
whose implementation is still outside `HEAD`; this Query slice does not absorb
that unrelated implementation.

## Remaining boundaries and non-goals

1. Granted QUERY execution has its own typed one-shot read and revalidation
   boundary; it likewise has no publication stage.
2. Legacy `QueryContextRef` intentionally authenticates its provider before
   opening concealed source content and remains unchanged.
3. `MemCommitClient.query_ordinary` now projects this internal result through
   the versioned Python types recorded in
   `query-public-python-api-design-rationale.md`; the internal request and
   response remain non-public implementation seams.
4. Provider and runtime configuration remain injected composition concerns;
   the public client freezes a Query-only non-secret snapshot but this use case
   still does not select a model, endpoint, timeout, or profile.

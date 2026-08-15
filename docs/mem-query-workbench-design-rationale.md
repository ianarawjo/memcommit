# Interactive Query workbench design rationale

## Problem

`mem query` historically overloaded its first positional `SELECTOR`. One value
could be an ordinary-Context question, a public query-only View, a
`VIEW#HANDLE`, or a legacy reference. With no value, the callback returned a
usage error before resolving the current Context or connecting a provider.
That contract preserved explicit scripts but prevented Query from offering the
same query-first terminal entry point as Find.

Query also has two materially different Source boundaries. Ordinary Query reads
visible Contexts and synthesizes a grounded answer from the complete frozen
candidate corpus in one provider turn.
Query-only View execution receives only public grant routing metadata until the
query provider is authenticated; it then opens concealed authority material,
revalidates the grant and source after the provider call, and may save only the
visible Q/A transcript when `SESSION_LOG` is granted. Treating both as plain
Context strings would erase this distinction.

## Decision

In a TTY, bare `mem query` opens a process-local workbench with visible frames
in this order:

1. `QUESTION`, initially focused and blank;
2. `SOURCES`, showing either the shared Profile/Context range selector or a
   typed list of public query-only Views;
3. `SCOPE`, whose controls depend on Source type;
4. optional `SESSION NAME`, visible only for query-only transcript logging; and
5. `ANSWER`.

The ordinary Scope reuses `ContextRangeSelectionState`: `PROFILE`, one versus
many roots, exact versus descendant rows, and embedded-Context traversal remain
independent. Execution freezes the exact effective checked names so an
independently cleared descendant cannot be silently reintroduced. The
query-only Scope instead exposes exact View versus relevant-descendant
federation and one-shot versus visible-Q/A session logging. Language remains an
explicit command option and is displayed in the workbench.

No provider connects merely because the workbench opens or a cursor moves.
Enter in `QUESTION` freezes one typed request and runs it through the shared
background-turn lifecycle. `ANSWER · QUERYING …` and the footer both display
progress. A blank ordinary question is rejected before connection. A blank
question with a selected query-only View retains the established safe catalog
browse: only opaque handles and shape placeholders are rendered.

Escape uses the shared hierarchical back dispatcher. From Sources, Scope,
Answer, or the optional Session Name field it returns to the Question field
without submitting; from Question it closes the workbench. Backspace mirrors
the one-level return only on read-only Surfaces and remains ordinary deletion
inside Question or Session Name. Closing while a provider turn is in flight
retains the existing deferred-close boundary.

An ordinary grounded answer retains a typed citation document alongside its
unchanged CLI string. `ANSWER` treats the neutral answer body and each used
Reference as one linear Up/Down sequence. Moving onto a Reference anchors that
block in the viewport and gives the complete metadata-and-excerpt block the
shared blue focused-control background; leaving Answer retains the blue
selection without bold focus. This structure comes from the citation renderer
and is never reconstructed by parsing `References` out of finished text.

While `ANSWER` owns focus, lowercase `y` copies exactly that typed focus unit:
the answer body at stop zero or the complete numbered metadata-and-excerpt
block for the active Reference. Uppercase `Y` copies the complete typed answer
document in body-then-References order. A granted answer, granted catalog, or
saved transcript has no finer typed stop, so `y` copies that displayed document
and `Y` produces the same complete document. Clipboard projection runs before
terminal wrapping and escapes terminal controls through the same display
boundary, so pasted text has neither viewport line breaks nor ANSI styling.

These keys are bound only on the read-only Answer Surface. Both characters
remain ordinary text in `QUESTION`, `SESSION NAME`, and every other writable
field. A successful `COPIED` receipt or a nonfatal `COPY FAILED` receipt is
shown in the footer; neither closes the workbench nor changes answer focus.
The action writes only the operating-system plain-text clipboard. It does not
create the private structured clipboard stage used by mutation-oriented
commands, save a transcript, or grant authority over any cited Source.

Outside a TTY, a selector remains required because there is no interactive
surface in which to supply a question or Source. All existing explicit forms
remain compatible.

## Shared execution boundary

Ordinary Query now crosses the terminal-independent
`operations/query/ordinary_application.py` request, frozen-source,
provider-ordering, and response boundary. `ordinary_runtime.py` supplies the
`MemoryStore` and readable-catalog adapter. Granted Query separately crosses
`granted_application.py`, whose answer/catalog read returns an optional
still-unpublished session-turn plan, and `granted_runtime.py`, whose publication
adapter independently revalidates `SESSION_LOG`, Source freshness, and the
session CAS. The local `QueryContextRef` route crosses
`reference_application.py` and `reference_runtime.py`; its provider factory is
deliberately invoked before the runtime may open concealed Source content. CLI
and TTY import the operation package directly, while the former top-level
module paths remain implementation-free compatibility exports. The former
`commands/query_execution.py` progress facade was removed after production,
tests, and capture tools moved to the direct operation runtime:

- `OrdinaryQueryRequest` freezes question, exact public Context names,
  descendant policy, and embed policy. It has no top-k evidence limit.
- `FindAnswerReferenceDocument` retains the rendered answer body and numbered
  used References while its `text` property preserves the established CLI
  output byte-for-byte.
- `GrantedQueryRequest` freezes a public control-plane grant target, question or
  catalog mode, language, optional opaque Memory handle, session name, and
  federation policy.
- `QueryReferenceRequest` freezes one local concealed Source UID/name,
  persisted provider identifier, question, and language without importing
  terminal or Store types into the application contract.

The CLI continues to resolve its overloaded positional grammar for backward
compatibility, then constructs one of these typed requests. The workbench never
re-enters that string inference path. Presentation and progress stay in the
calling adapter. For ordinary Query, readable evidence freezes and whole-frame
preflight completes before the injected provider factory is called, and no
durable effect exists. For granted Query, provider construction still precedes
concealed-source opening; the read releases an answer only after route and
Source revalidation. Merely returning its process-local publication plan does
not write. The optional append is a second use case that rechecks current
authority and Source identity before the profile-guarded, locked CAS write.
For a local `QueryContextRef`, provider construction completes before the Store
adapter opens the exact Source UID/name/language projection; the returned
answer has no durable effect.

## Authority and persistence invariants

- The ordinary Source tree is frozen through `ReadableContextCatalog`; READ
  grants retain their exact access binding and query-only sources never enter
  its candidate corpus.
- A granted current Context remains the initial checked row but does not narrow
  `PROFILE`: the tree still contains the active Profile's local Contexts and all
  other valid READ-granted public names.
- Query-only Source discovery reads only active grant and local attachment
  metadata. It does not open authority source content.
- Authentication precedes concealed source loading.
- Every published query-only answer is preceded by a post-provider grant and
  source-binding recheck under the registry snapshot lock.
- A completed session-shaped read is not publication authority. The separate
  append rechecks `SESSION_LOG` and the Source binding under a fresh authority
  snapshot, then CAS-checks the exact visible transcript snapshot.
- Federation offers only public descendant names to its routing turn and opens
  only the returned authorized subset.
- Saved sessions remain bound to one exact grant/source/language projection and
  persist visible questions and answers only. Federation is disabled for a
  saved session.
- Workbench cursor, Source type, Scope, question drafts, and one-shot answers
  are process-local. Ordinary Query does not create a session.

## Alternatives and limitations

Calling the Typer callback from inside the TUI was rejected because its direct
stdout and progress rendering would corrupt the full-screen terminal and would
retain ambiguous string routing inside the interactive state. Duplicating the
Find workbench was also rejected; Query instead reuses the shared Context range,
Surface focus, horizontal choice, flat selection, background lifecycle, and
Frame styling components.

The first workbench edits language through the existing CLI option rather than
adding another free-form field. Legacy `QueryContextRef` selectors and exact
`#HANDLE` authoring remain explicit CLI routes, while a query-only catalog
displayed in the workbench shows the handles needed for that explicit route.
Command-C was not selected as the semantic binding because terminal emulators
normally consume the Command modifier for their own selection copy and do not
portably forward it to prompt-toolkit. Ctrl-C therefore retains close semantics,
and `y`/`Y` provide a terminal-native focused-versus-complete distinction.

## Interface ownership

The workbench implementation now lives under
`interfaces/tui/operations/query/` as separate model, typed projection adapter,
and prompt-toolkit screen modules. The command imports that owner directly;
`commands/query_workbench.py` is an implementation-free compatibility export.
Shared activity, background-turn, horizontal-choice, and plain-text clipboard
mechanics are likewise interface-owned. Session Help remains command-composed
and is injected into the screen because its inventory depends on the Typer root
command rather than Query semantics. The detailed dependency decision and
verification are recorded in `query-tui-interface-design-rationale.md`.

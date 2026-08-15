# QueryContextRef application-boundary matrix

Last verified: 2026-08-15.

## Problem

The original `QueryContextRef` route kept concealed Query Source records outside
the ordinary Context namespace, but its complete execution lived in
`commands/query.py`: provider construction, Source opening, inference,
progress, error rendering, and stdout were one command-owned function. That
made the CLI the only callable entry point and obscured the critical privacy
order that provider authentication must finish before concealed content is
opened.

This route is called legacy only to distinguish its local `QueryContextRef`
storage contract from authority-granted Query views. It remains supported
behavior and is not being silently converted into a Grant or ordinary READ
operation.

## Decision

`memcommit.query_reference_application` owns the typed request, frozen Source,
provider/source ports, exact response, stage observer, and use-case ordering.
`memcommit.query_reference_runtime` adapts `MemoryStore.load_query_source` to
that contract. The command resolves the `QueryContextRef`, constructs the
request, projects stages into the existing progress display, renders safe
errors, and prints the returned answer.

```text
CLI selector resolution
        |
        v
QueryReferenceRequest
        |
        v
construct/authenticate configured provider
        |
        v
open exact concealed Source uid/name/language
        |
        v
one provider query over the complete selected language frame
        |
        v
QueryReferenceResponse ----> CLI safe text rendering
```

No function is split merely to make one file per function. The application
module groups the values and orchestration that change with the use-case
contract; the runtime module groups Store integration that changes with
infrastructure. CLI presentation remains a separate responsibility.

## Responsibility matrix

| Boundary | Owner | Invariant |
| --- | --- | --- |
| Reference resolution | CLI adapter | Only an already resolved `QueryContextRef` enters this use case |
| Request | `QueryReferenceRequest` | Exact Source UID, expected public name, provider name, nonblank question, and language are frozen together |
| Provider construction | Application plus injected factory | Completes before the Source port is called |
| Concealed Source | Runtime Source port | Loads only the exact UID/name/language projection through `MemoryStore.load_query_source` |
| Provider disclosure | Application | One provider query receives the complete selected Source content and exact question |
| Response | `QueryReferenceResponse` | Retains the exact request and provider-returned text; no terminal behavior |
| Durable effect | None | No Context, checkpoint, current pointer, session, transcript, cache, or receipt is written |
| Presentation | CLI adapter | Existing progress labels, safe error prefix, and answer output remain terminal-owned |

## Preserved behavior

- `codex_chatgpt` and any other persisted provider identifier still route
  through the existing injected connector.
- A provider connection failure occurs before `load_query_source`; concealed
  text remains unopened.
- The Source UID and expected name must still match, and language selection
  still requires complete coverage unless the Store contract says otherwise.
- The provider still receives the Source's public name, complete selected
  content, and question exactly once.
- Successful output remains the answer plus one terminal newline.
- The route remains one-shot: `--session` is rejected by CLI routing and no
  visible question or answer is persisted.
- Existing progress remains `connecting provider` followed by
  `answering query`.

No TUI surface uses this route, and this extraction changes no visible flow,
focus topology, key binding, output wording, provider policy, Source schema, or
command grammar. New terminal snapshots are therefore unnecessary.

## Alternatives and limitations

Leaving provider construction in the command and extracting only Source
loading was rejected because the privacy ordering would still be implicit in
one adapter. Reusing the granted Query application was rejected because a
local `QueryContextRef` has no Grant registry, public-view federation,
post-provider authority revalidation, or `SESSION_LOG` capability. Reusing
ordinary Query was rejected because concealed Query Sources are deliberately
outside the READable Context corpus.

The callable is internal, not yet a versioned public Python or agent API. The
CLI still owns overloaded selector routing, and the Query TUI still lives in
`commands/query_workbench.py`; moving those interface files is the next
structural step after every Query execution route is terminal-independent.

## Verification

`tests/test_query_reference_application.py` proves provider-before-Source
ordering, provider-free Source protection on authentication failure, typed
input validation, exact language selection, no filesystem mutation, no
terminal output, Source-identity rejection after provider construction, module
dependency direction, and production-adapter ownership. Existing
`tests/test_query_only.py` cases continue to verify CLI output, complete
language projection, provider authentication order, and absence of
checkpointing or transcript persistence.

The complete current-worktree Query application, QueryContextRef, grant,
session, answer, and workbench run passed 99 tests. A separate provider and
progress run passed 26 tests and retained one unrelated pre-existing failure:
the concurrent Find/ordinary-Query provider-policy test expects the opposite
model order from the current implementation. This extraction does not select
or change either model.

The exact staged tree passed Ruff, both new-module type checks, all 11 new
boundary tests, and 52 non-CLI Query application and workbench tests. Its CLI
collection remains gated by the pre-existing committed Summarize import of
`declared_artifact_available`, whose implementation is still outside `HEAD`;
this Query slice does not absorb that unrelated function.

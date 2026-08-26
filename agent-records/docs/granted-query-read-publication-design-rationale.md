# Granted Query one-shot read boundary

Last verified: 2026-08-26.

## Decision

Granted Query has one effect: a revalidated, process-local read of concealed
authority material. The former second phase that published visible Q/A to a
named session has been removed from application contracts, Store adapters,
public API results, agent payloads, CLI grammar, and the TUI.

```text
public target + one question
            |
            v
 freeze QUERY grant identity
            |
            v
construct/authenticate provider
            |
            v
open exact concealed Source frame
            |
            v
route allowed descendants if requested
            |
            v
       produce answer
            |
            v
revalidate grant + Source binding
            |
            v
release process-local response
```

`GrantedQueryRequest` freezes grant UID, public name, attachment name, a
required nonblank question, language, and federation policy.
`GrantedQueryResponse` contains one answer. There is no per-Memory catalog,
handle selector, unpublished turn, publication token,
publication receipt, record digest, session name, or Store write port.

## Responsibility matrix

| Boundary | Owner | Invariant |
| --- | --- | --- |
| Public input | `GrantedQueryRequest` | One immutable public target and one-shot query intent |
| Pre-provider authority | runtime prepare adapter | Requires current `QUERY` before provider construction |
| Provider disclosure | runtime read adapter | Concealed Source opens only after provider construction succeeds |
| Source frame | granted Source adapter | Complete authorized View content opens only after provider construction and never returns to the caller |
| Federation | runtime routing adapter | Provider sees public descendant names only; only selected authorized bindings open |
| Answer | runtime read adapter | Root and selected descendant bindings revalidate before response release |
| Retention | none | Query creates no transcript, publication plan, receipt, or search artifact |

## Failure and no-write matrix

| Case | Provider constructed | Concealed Source opened | Answer released | Store write |
| --- | ---: | ---: | ---: | ---: |
| Missing QUERY authority | No | No | No | No |
| Provider construction failure | Attempted | No | No | No |
| Missing question | No | No | No | No |
| Grant or Source changes during inference | Yes | Yes | No | No |
| Successful one-shot answer | Yes | Yes | Yes | No |

Revocation during the provider turn may surface as the current Profile or
Source error type, but the important contract is that the answer is never
released after failed revalidation.

## Compatibility

The old top-level granted Query modules remain thin implementation-free export
facades for the surviving request, response, and execution names. The runtime
keeps `execute_granted_query_request` as an alias of the one-shot read entry
point. Removed session-publication symbols are intentionally not emulated.

Legacy Profile registry values containing `SESSION_LOG` normalize to `QUERY`
during load. This prevents a retired capability string from breaking Profile
startup without reintroducing a publication path. Legacy on-disk transcript
records are ignored and not automatically deleted.

## Alternatives considered

- **Leave a no-op publication receipt:** rejected because it would falsely
  promise a durable effect and preserve an unusable API surface.
- **Retain the Store adapter behind a hidden flag:** rejected because hidden
  retention is still a data-lifecycle feature and still diverges from TUI/CLI
  parity.
- **Release the answer before revalidation:** rejected because revocation or
  Source drift during inference must fail closed.
- **Open the Source before connecting the provider:** rejected because provider
  authentication is part of the concealed-data disclosure boundary.

## Verification

`tests/test_granted_query_application.py` covers application ordering,
provider stages, zero storage, and revocation during a turn.
`tests/test_granted_query_sources.py` covers complete-View scoping,
federation, translation, Source drift, and the absence of Query-session
storage. Public API and agent tests assert one-shot response schemas with no
session receipt or publication error.

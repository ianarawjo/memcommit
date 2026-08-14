# Granted Query read and session-publication boundary

Last verified: 2026-08-14.

## Problem

A granted Query has two effects that were previously implemented in one
command-owned function. Opening a catalog or producing an answer is a
revalidated read of concealed authority material. Appending the visible
question and answer to a named Query session is a durable write owned by the
active grantee store. Combining both effects made the answer function the only
callable entry point and made it impossible for another adapter to request an
answer without also publishing the requested session turn.

The split must not weaken the established privacy order. Provider
authentication must still precede concealed Source loading, answers must still
be withheld if a grant or Source changes during inference, and a completed
answer must never be treated as continuing `SESSION_LOG` authority.

## Decision

`memcommit.granted_query_application` owns terminal-independent request,
response, unpublished-turn, publication-receipt, port, and orchestration
contracts. `memcommit.granted_query_runtime` owns the `MemoryStore`, authority,
Source-loading, federation, session-store, lock, and CAS adapters.

The read use case returns `GrantedQueryReadOutcome`. A session request includes
an opaque `GrantedQuerySessionPublication`, but that value is only an intent to
append the exact answered turn. Reading it, returning it, or discarding it does
not create a session directory or record. Only the separate publication use
case may make it durable.

```text
public target + question/session intent
                    |
                    v
         freeze required grant permission
                    |
                    v
          construct/authenticate provider
                    |
                    v
    open catalog or exact concealed Source frame
                    |
                    v
       route allowed descendants when eligible
                    |
                    v
              produce answer
                    |
                    v
       revalidate grant + every Source binding
                    |
          +---------+------------------+
          |                            |
          v                            v
 revalidated response       unpublished session-turn plan
                                       |
                         explicit publication use case
                                       |
                     revalidate SESSION_LOG + Source again
                                       |
                         CAS append exactly one turn
```

The CLI and TUI call the Store-backed runtime directly. The old
`commands.query_execution.run_granted_query_request` remains a compatibility
composition that executes the read and, only when the outcome contains a
publication plan, explicitly invokes publication. It contains no granted
Query implementation.

## Responsibility matrix

| Boundary | Owner | Invariant |
| --- | --- | --- |
| Public input | `GrantedQueryRequest` | Freezes grant UID, public and attachment names, catalog/answer mode, language, handle, federation, and optional session intent |
| Capability display | `GrantedQueryTarget.session_log_allowed` | UI hint only; runtime registry state remains authoritative |
| Pre-provider authority | read Store adapter | Requires `QUERY`, or `SESSION_LOG` for a saved turn, before provider construction |
| Provider disclosure | read Store adapter | Concealed Source content opens only after provider construction succeeds |
| Catalog | read Store adapter | Catalog is loaded twice across an authority snapshot check and is never persisted |
| Answer | read Store adapter | Root and every selected descendant binding are revalidated after the provider returns and before the answer is released |
| Existing session | `QuerySessionStore.load_or_start` | Reads visible prior Q/A and strict binding without creating storage |
| Publication plan | application value plus opaque runtime token | Binds the exact request, answer, Source digest, session snapshot, expected record digest, and Store root; grants no write by itself |
| Durable publication | publication Store adapter | Rechecks current `SESSION_LOG` and Source binding, then performs one profile-guarded, locked CAS append |
| Receipt | `GrantedQuerySessionPublicationResult` | Reports session name, resulting revision, and turn count only after the append succeeds |

## Preserved behavior

- Catalog browsing still authenticates the provider before opening authority
  Memories, even though it does not call the provider afterward.
- A one-shot answer still uses `QUERY`; a saved turn still requires the
  distinct `SESSION_LOG` permission before provider construction.
- Relevant-descendant routing still sees public names only, opens only the
  selected authorized views, and remains disabled for saved sessions and
  opaque Memory-handle requests.
- Saved dialogue still reconstructs provider input from visible prior Q/A and
  persists only visible question/answer text plus opaque freshness bindings.
- The command compatibility entry point retains its argument order, result,
  and three established progress callbacks. The new internal revalidation and
  publication stages are not projected as new terminal output.
- Replay of one publication plan fails its expected-record-digest CAS rather
  than appending the same turn twice.

No TUI frame, focus order, key binding, output wording, provider policy,
session schema, file mode, federation rule, or command-line grammar changes in
this slice. Therefore no new terminal snapshots are required.

## Failure and no-write matrix

| Case | Provider called | Answer returned | Session write |
| --- | ---: | ---: | ---: |
| Missing required permission at preparation | No | No | No |
| Provider construction failure | No concealed Source opened | No | No |
| Grant or Source changes during answer generation | Yes | No | No |
| Session read completes and publication plan is discarded | Yes | Yes | No |
| Grant revoked after read but before publication | Already complete | Already returned to caller | No |
| Source changes after read but before publication | Already complete | Already returned to caller | No |
| Session changes concurrently or plan is replayed | Already complete | Already returned to caller | No additional turn |
| Explicit publication with fresh grant, Source, and session snapshot | Already complete | Yes | Exactly one CAS append |

The read/publish gap deliberately means a caller may already possess a valid
answer when later publication authority disappears. Publication failure does
not retract that earlier authorized read; it prevents only the durable effect.

## Alternatives and limitations

Keeping a Boolean such as `save_session=True` inside one answer function was
rejected because omission and publication would still share one effectful
contract. Publishing immediately and returning only a saved receipt was
rejected because nonterminal adapters could not safely obtain a read-only
answer for a session-shaped request. Treating the target's
`session_log_allowed` field as authority was rejected because it is a frozen
display hint that can become stale.

The publication plan is process-local and intentionally opaque. It is not a
portable receipt, cache artifact, public Python API, or agent-tool payload.
Catalog and answer reads still depend on the existing authority registry and
Source projection implementation. Legacy `QueryContextRef`, transcript
listing/viewing, provider configuration, and public API versioning remain
separate work.

## Verification

`tests/test_granted_query_application.py` proves application ordering,
publication opt-in, zero-write read behavior, exactly-one append, replay/CAS
rejection, answer-substitution rejection, grant revocation after read, Source
change after read, and interface dependency direction. Existing granted Query
tests continue to prove catalog,
opaque-handle, federation, translation, provider-time revocation, stale
session, file-permission, size-bound, and visible-Q/A behavior.

The focused current-worktree run passed 69 application, workbench, granted
session, and query-only tests. An expanded Query run passed 116 tests before
one unrelated concurrent provider-policy expectation failed because its Find
and Query model order no longer matched the implementation. The exact staged
tree passed Ruff, both application/runtime type checks, all seven new boundary
tests, and 55 non-CLI Query application/provider/workbench tests. Its broader
CLI collection remains gated by the pre-existing committed Summarize import of
`declared_artifact_available`, whose implementation is outside `HEAD`; this
Query change does not absorb that unrelated function.

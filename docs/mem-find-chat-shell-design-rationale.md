# Interactive Find chat and read-only action rationale

## Problem

`mem find` needs a conversational surface because a person often cannot know
the useful result set or next operation before seeing semantic matches.
Directly copying Ground's Goal--Rules--Cases shell would couple Find to
Ground-specific provider responses, approval semantics, and persistence.
Allowing a provider to return arbitrary command text would instead turn result
interpretation into command authority.

## Decision

`find_chat_shell.py` imports only the operation-neutral terminal assets:

- vertical TUI regions and frame composition;
- interactive-terminal validation;
- terminal-safe text; and
- viewport anchoring.

It presents a controller-supplied header, transcript, and locally validated
result rows grouped by their owning Context. Result text comes from typed
`FindChatResult` values supplied by the local controller, not from generated
provider prose. Dialogue and results use separate scrollable panels so a
growing transcript cannot hide the ranked result set after a follow-up turn.
The shell collects one nonblank user turn, returns a typed
`SUBMIT` or `CLOSE` action, and exits. It does not:

- call the semantic provider;
- search a Context;
- execute a command;
- persist dialogue or a Find session;
- copy to the clipboard;
- create a Context or checkpoint; or
- own kept-item identity.

The command controller owns those effects outside prompt-toolkit's key
handler. In a TTY, ordinary `mem find QUERY` performs the validated initial
search and opens the workbench. Outside a TTY, its established grouped text
output remains unchanged for scripts, redirection, and tests.

The `run_find_chat_session` controller loop exercises the shell boundary:
it receives `SUBMIT`, calls an injected turn handler only after the full-screen
application has exited, and reopens the shell with the returned complete view.
A failed turn preserves the previous results, displays the failure as a new
visible status block, and waits for another explicit input. Provider latency
therefore cannot block a prompt-toolkit key handler.

The result panel uses a read-only text buffer rather than a cursorless
formatted-text control. Its hidden cursor moves with the result-panel arrow
keys, giving prompt-toolkit a real scroll anchor while keeping result content
immutable.

## Agent-mediated `SHOW_RESULT`

The first complete follow-up action is deliberately narrow:

```text
“show the third result”
→ provider returns SHOW_RESULT + m3
→ host resolves m3 to the visible Context and full item UID
→ host constructs mem show FULL_UID --context OWNER
→ normal CLI path runs once without a shell
→ actual stdout is appended and the Find view reopens
```

Every displayed result receives a stable local alias such as `m1`. The
provider receives aliases, visible result content, public Context names, and
the submitted turn. When it previously returned `ASK`, the next one-shot turn
also receives that last visible understanding and question so replies such as
“the latter” retain their referent. Command receipts and status blocks are not
replayed. The provider does not receive durable Memory UIDs or command
authority. Query-only results expose only their already-public name and
`query-only` label, never their concealed source.

The strict response union contains only `ASK` and `SHOW_RESULT`. `ASK` requires
an empty selector; `SHOW_RESULT` requires exactly one alias enumerated in the
current schema. Unknown aliases, extra command fields, malformed output, and
unsupported action kinds fail closed.

The host creates an immutable `ExactCommandReview` only after resolving the
alias locally. Here it is used as an injectively escaped command/effect receipt,
not as a second approval gate: `mem show` is proven read-only, uses an explicit
owner Context, does not change the current Context, and was explicitly
requested in the submitted turn. The runner accepts only the exact
`mem show ITEM --context CONTEXT` shape, invokes `python -m memcommit.cli`
without a shell, captures actual output, and rejects failure, timeout, or empty
stdout. Results and checkpoints remain unchanged.

This mirrors Ground's authority boundary while retaining operation-specific
semantics: the provider returns a typed intent, the host owns UID resolution
and argv, and the ordinary CLI remains the execution boundary. A future
state-changing Find action must additionally display a dedicated approval and
recheck frozen source versions before execution.

## Integration boundary

The current in-process view supplies:

1. locally validated ranked results with stable local aliases;
2. repeated ASK or read-only SHOW turns;
3. actual command output and failure receipts; and
4. separate dialogue, result, and input panes.

It intentionally does not yet provide durable resume, semantic re-ranking,
keep/unkeep, clipboard export, or materialization. Those actions require a
persisted `FindSession` with source versions and, for mutation, a separate
exact-command approval. This first vertical slice establishes the agent-to-CLI
orchestration pattern without pretending those later contracts already exist.

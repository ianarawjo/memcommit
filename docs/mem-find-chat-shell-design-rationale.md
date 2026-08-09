# Interactive Find chat and read-only action rationale

> Compatibility status: the shell and controller remain as tested internal
> components, but `mem find QUERY` no longer launches them and instead prints
> static grouped results and exits. Operand-free `mem find` uses the distinct
> query-first search-and-scope workbench documented in
> `mem-find-search-workbench-design-rationale.md`. This document preserves the
> rationale for retained compatibility code rather than describing either
> active CLI entry path.

## Problem

`mem find` needs a conversational surface because a person often cannot know
the useful result set or next operation before seeing semantic matches.
Directly copying Ground's Goal--Rules--Memories shell would couple Find to
Ground-specific provider responses, approval semantics, and persistence.
Allowing a provider to return arbitrary command text would instead turn result
interpretation into command authority.

## Decision

`find_chat_shell.py` imports only the operation-neutral terminal assets:

- vertical TUI regions and frame composition;
- interactive-terminal validation;
- terminal-safe text; and
- viewport anchoring.

It presents a controller-supplied header, locally validated result rows grouped
by their owning Context, the transcript, and the input in that visual order.
Result text comes from typed
`FindChatResult` values supplied by the local controller, not from generated
provider prose. Dialogue and results use separate scrollable panels so a
growing transcript cannot hide the ranked result set after a follow-up turn.
Each result also carries host-validated `primary` or `related` relevance. A
related-only view renders `PRIMARY MATCHES 0`, the bounded broader query, and a
separate `RELATED RESULTS` heading; it never folds fallback rows into the
primary count.
The production session keeps one full-screen `Application` alive from initial
results through repeated follow-up turns. A focused one-turn wrapper can still
return a typed `SUBMIT` or `CLOSE` action for input-only callers and tests. The
presentation layer does not itself:

- call the semantic provider;
- search a Context;
- execute a command;
- persist dialogue or a Find session;
- copy to the clipboard;
- create a Context or checkpoint; or
- own kept-item identity.

The injected command controller owns those effects outside prompt-toolkit's
key handler. In a TTY, ordinary `mem find QUERY` performs the validated initial
search and opens the workbench. Outside a TTY, its established grouped text
output remains unchanged for scripts, redirection, and tests.

On submit, `run_find_chat_session` freezes the committed `FindChatState` and
input, clears and disables the composer, renders the submitted turn with
`THINKING · RESULTS UNCHANGED`, and schedules one managed background task. The
task runs the synchronous controller in an executor thread. Only after awaiting
that work does the event-loop thread replace the committed state and update the
read-only result and dialogue `Document` values. The `Application`, widgets,
alternate screen, and result scroll position therefore remain alive throughout
the turn. While it runs, the input heading cycles through
`PROCESSING FIND TURN .`, `..`, and `…` on an event-loop timer. The animation
only invalidates the prompt-toolkit view; it does not poll, restart, or duplicate
provider work.

Only one controller turn may be in flight. A failed turn preserves the
previous committed results, appends a visible failure receipt in the same
screen, and re-enables input. Provider latency does not block a prompt-toolkit
key handler or make the terminal appear to leave Find.

The result panel uses a read-only text buffer rather than a cursorless
formatted-text control. Its hidden cursor moves with the result-panel arrow
keys, giving prompt-toolkit a real scroll anchor while keeping result content
immutable. The dialogue panel uses the same kind of read-only buffer, opens at
the latest line, and supports arrow and page scrolling. Long numbered
references therefore remain inspectable instead of disappearing above a
cursorless eight-line viewport.

## Agent-mediated refinement, answers, and `SHOW_RESULT`

The first command-backed follow-up action is deliberately narrow:

```text
“show the third result”
→ provider returns SHOW_RESULT + m3
→ host resolves m3 to the visible Context and full item UID
→ host constructs mem show FULL_UID --context OWNER
→ normal CLI path runs once without a shell
→ actual stdout is appended to the same live Find view
```

Every displayed result receives a stable local alias such as `m1`. The
provider receives aliases, visible result content, public Context names, and
the submitted turn. When it previously returned `ASK`, the next one-shot turn
also receives that last visible understanding and question so replies such as
“the latter” retain their referent. Command receipts and status blocks are not
replayed. The provider does not receive durable Memory UIDs or command
authority. Query-only results expose only their already-public name and
`query-only` label, never their concealed source.

The strict first response is a plan union containing `ASK`, `REFINE`, `ANSWER`,
and `SHOW_RESULT`. `REFINE` carries one bounded standalone query and asks the
host to rerank the same frozen candidate frame. It replaces the visible result
set, resets process-local kept count, and updates the displayed query; it does
not load another Context or mutate stored data. A concrete topic, keyword set,
constraint, or broader/narrower description is a refinement. In particular,
when zero results are visible, a concrete phrase such as “related to healthcare”
must trigger `REFINE` rather than an unnecessary `ASK`.

A related fallback is still a visible result for read-only inspection, so its
alias may be selected by `SHOW_RESULT`. It is not evidence that the original
query was satisfied. When every visible row is related, the strict plan schema
offers `ASK`, `REFINE`, and `SHOW_RESULT` but omits `ANSWER`. The controller
also checks this invariant before synthesis so malformed or bypassed intent
output cannot turn a broader-topic row into an answer about the original query.

`ANSWER` does not contain answer prose. It requests a separate host-controlled
evidence turn and selects either `CONTEXT` or `ALL_CONTEXTS`.
The latter is valid only when the person explicitly asks to inspect other
Contexts. `ASK` is reserved for an ambiguous request. `SHOW_RESULT` requires
exactly one alias enumerated in the current schema. Unknown aliases, extra
fields, incompatible scope values, malformed output, and unsupported action
kinds fail closed. An `ALL_CONTEXTS` plan does not open other Contexts. It
creates a visible pending request that explains the additional provider
disclosure and requires the exact host-owned token `confirm other contexts` in
a separate submitted turn. `cancel other contexts` clears the pending request;
any other reply leaves it pending. Thus an over-broad or injected provider plan
cannot expand disclosure, and natural-language classification is not treated
as an authority boundary.

For `ANSWER`, the controller constructs three evidence scopes:

1. the visible ranked results, projected as `mN`;
2. the remainder of the frozen initial search frame, projected as `cN`; and
3. deduplicated direct items in other stored Contexts, projected as `xN`.

The second scope is checked automatically because it remains inside the
selected search frame. The third is collected only after an `ALL_CONTEXTS`
plan and the separate exact confirmation turn. A recursive Find treats every
materialized Context below the selected canonical `NAME/` prefix, together
with reachable explicit embeds, as part of the frame. With `--direct`, both
namespace descendants and embedded children are outside that frame. The
namespace-root set is frozen before initial ranking and reused for the
interactive controller, so a result cannot disappear merely because it was
reached lexically rather than through an embed.

A second strict provider completion receives those temporary aliases and their
local projections, but no durable UIDs. It returns exactly one bounded text
field and a scope-local alias list for each of the three scopes. The prompt
requires three natural sentences, in scope order, and distinguishes:

- a scope that was not requested;
- a completed scan with no additional evidence found; and
- a partial or unavailable scan.

The wording deliberately avoids claiming that a semantic scan proves
non-existence. The local parser proves schema shape, alias membership,
scope membership, and visible-result provenance. It cannot mechanically prove
that each natural-language claim is entailed by its cited contents or that
each text field contains grammatically one sentence in every language; those
remain prompt-level prototype constraints.

When a same-frame or searched other-Context sentence cites no evidence, the
host replaces its prose with a factual localized scope-status sentence. The
host also owns the `NOT_REQUESTED` and `UNAVAILABLE` sentences regardless of
provider prose. This prevents a source-free generated sentence from claiming
facts about a scope that was never checked. A `PARTIAL` response with cited
evidence may still summarize that evidence, while the prompt requires it to
state that the wider check was incomplete.

The provider never writes citation numbers. After validation, the host assigns
`[1]`, `[2]`, and later numbers by first citation occurrence, appends them to
the three sentences, and renders a `References` section below. Each used
reference includes its temporary alias, local type, UID prefix, owning Context,
and the complete locally projected content. Repeated citations reuse one
number, uncited candidates are omitted, and an unknown alias fails closed.
Generated sentences may not contain host-style numeric markers or line breaks.
Stored content is indented beneath reference metadata so text such as
`References` or `[77]` inside a Memory cannot imitate host structure. Terminal
escaping remains at the shell display boundary.

Query-only items contribute only their displayed public name and `query-only`
label in every scope and reference. Their concealed source is neither loaded
nor transmitted. An `ANSWER` turn executes no command and changes no Context,
checkpoint, result, or current-Context state.
`ASK` and `SHOW_RESULT` use one provider completion. `REFINE` uses the intent
completion and then one validated ranking completion over the already frozen
frame. A same-frame `ANSWER` uses the intent completion and then the separate
synthesis completion. An other-Context answer pauses between those completions
for the exact confirmation turn.

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

1. locally validated primary or explicitly related ranked results with stable
   local aliases and separate counts;
2. repeated same-frame REFINE, ASK, three-scope grounded ANSWER, or read-only
   SHOW turns;
3. actual command output and failure receipts;
4. result, dialogue, and input panes in reading order; and
5. stable widget identity and scroll state across completed follow-up turns.

The committed `FindChatState` changes only after a controller turn completes
or is converted into a visible failure receipt. `THINKING` and a requested
close are transient view states. While a turn is in flight, the composer is
read-only and a second turn cannot be queued against stale state.

It intentionally does not yet provide durable resume, keep/unkeep, clipboard
export, or materialization. Reranking is process-local and never expands the
frozen initial frame. An explicitly requested other-Context collection reads
multiple current Context records without one store-wide atomic snapshot. Its
answer must therefore describe what this scan found rather than assert a
timeless global absence. Durable selections and later mutations require a
persisted `FindSession` with source versions and a separate exact-command
approval. This vertical slice establishes the agent-to-CLI orchestration
pattern without pretending those later contracts already exist.

The answer path requires at least one primary result. The show path may inspect
either tier because it renders one canonical local item without treating it as
support for the query. When ranking returns neither primary nor related
results, the first-turn schema permits `ASK` or `REFINE`: a concrete new search
description reranks the frozen frame, while a genuinely ambiguous turn may
still ask one question. It does not use broader evidence scopes to manufacture
an answer.
The pending other-Context request and its confirmation exist only in this
in-process view; they are not a durable or resumable approval.

The controller and its provider subprocess are currently synchronous. The
executor boundary keeps the terminal responsive but cannot forcibly cancel
that work. If the person requests close while a turn is running, the view
therefore shows that it is closing and waits for the bounded turn to finish
before leaving the alternate screen. Ctrl-D follows that same visible close
path. If the input stream itself disappears, prompt-toolkit must tear down the
screen immediately; the managed task still waits for the non-cancellable
worker and preserves its completed state in the returned session result.
Immediate cancellation remains a deliberate non-goal until the provider
boundary can own, terminate, and reap a cancellable child process.

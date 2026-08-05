import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.granted_context import GrantedReadStore, resolve_context_access
from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    format_exact_command,
)
from memcommit.commands.find_chat_shell import (
    FindChatMessage,
    FindChatResult,
    FindChatSessionResult,
    FindChatState,
    FindPendingAnswerRequest,
    run_find_chat_session,
)
from memcommit.commands.history_picker import choose_history
from memcommit.commands.history_present import (
    history_result_recovery_label,
    history_result_picker_entries,
)
from memcommit.commands.tui_primitives import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.find_answer_dialogue import (
    FindAnswerCorpusTooLarge,
    FindAnswerProvider,
    FindOutsideStatus,
    synthesize_find_answer,
)
from memcommit.find_answer_references import (
    render_find_answer_references,
)
from memcommit.find_scope_evidence import (
    collect_outside_context_evidence,
    compact_artifact_references,
    context_remainder_evidence,
    frame_context_uids,
    visible_result_evidence,
)
from memcommit.find_turn_dialogue import (
    FindTurnAction,
    FindTurnAnswer,
    FindTurnAsk,
    FindTurnRefine,
    interpret_find_turn,
)
from memcommit.history import HistoryError, build_history
from memcommit.history_search import (
    HistorySearchError,
    HistorySearchResult,
    is_temporal_query,
    search_history,
)
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.search import (
    FindError,
    SearchArtifact,
    SearchCandidate,
    SearchMatch,
    append_artifact_candidates,
    collect_candidates_from_roots,
    rank_candidates,
)
from memcommit.search_artifacts import collect_search_artifacts
from memcommit.store import MemoryStore
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError


FIND_OUTSIDE_CONFIRMATION = "confirm other contexts"
FIND_OUTSIDE_CANCELLATION = "cancel other contexts"


def _outside_confirmation_message(user_text: str) -> str:
    korean = any("\uac00" <= character <= "\ud7a3" for character in user_text)
    if korean:
        return (
            "다른 저장 Context를 확인하면 그 안의 일반 Memory 내용도 "
            "이 답변을 만드는 provider에 전송됩니다.\n\n"
            f"계속하려면 정확히 `{FIND_OUTSIDE_CONFIRMATION}`를, "
            f"취소하려면 `{FIND_OUTSIDE_CANCELLATION}`를 입력하세요."
        )
    return (
        "Checking other stored Contexts will also send their ordinary Memory "
        "contents to the answer provider.\n\n"
        f"Type exactly `{FIND_OUTSIDE_CONFIRMATION}` to continue, or "
        f"`{FIND_OUTSIDE_CANCELLATION}` to cancel."
    )


def _pending_find_clarification(state: FindChatState) -> str | None:
    if state.status != "WAITING FOR CLARIFICATION · RESULTS UNCHANGED":
        return None
    return next(
        (message.text for message in reversed(state.messages) if message.role == "MEM"),
        None,
    )


@dataclass(frozen=True)
class FindShowProposal:
    """One locally resolved read-only command for a visible Find result."""

    action: FindTurnAction
    result: FindChatResult
    review: ExactCommandReview
    submitted_text: str


def _find_answer_status(outside_status: FindOutsideStatus) -> str:
    """Describe the scopes actually checked, not merely the requested scope."""
    return {
        "NOT_REQUESTED": ("ANSWERED · CONTEXT CHECKED · OTHER CONTEXTS NOT CHECKED"),
        "SEARCHED": ("ANSWERED · CONTEXT CHECKED · OTHER CONTEXTS CHECKED"),
        "PARTIAL": ("ANSWERED · CONTEXT CHECKED · OTHER CONTEXTS PARTIALLY CHECKED"),
        "UNAVAILABLE": (
            "ANSWERED · CONTEXT CHECKED · OTHER CONTEXTS NOT FULLY CHECKED"
        ),
    }[outside_status]


@dataclass(frozen=True)
class FindTurnController:
    """Frozen local evidence frame and provider orchestration for one Find."""

    store: MemoryStore
    root_context: Context
    frame_roots: tuple[Context, ...]
    recursive: bool
    limit: int
    frame_candidates: tuple[SearchCandidate, ...]

    def __call__(
        self,
        state: FindChatState,
        text: str,
    ) -> FindChatState:
        self._visible_candidates(state)
        if state.pending_answer is not None:
            return self._handle_scope_confirmation(state, text)
        provider = connect_codex_chatgpt_provider()
        turn = interpret_find_turn(state, text, provider)
        if isinstance(turn, FindTurnRefine):
            return self._refine(state, text, turn, provider)
        if isinstance(turn, FindTurnAnswer):
            pending_clarification = _pending_find_clarification(state)
            if turn.scope == "ALL_CONTEXTS":
                return replace(
                    state,
                    messages=(
                        *state.messages,
                        FindChatMessage(role="USER", text=text),
                        FindChatMessage(
                            role="MEM",
                            text=_outside_confirmation_message(text),
                        ),
                    ),
                    status="WAITING FOR OTHER CONTEXTS CONFIRMATION",
                    pending_answer=FindPendingAnswerRequest(
                        user_text=text,
                        interpreted_request=turn.understanding,
                        pending_clarification=pending_clarification,
                    ),
                )
            return self._answer(
                state,
                submitted_text=text,
                answer_question=text,
                interpreted_request=turn.understanding,
                pending_clarification=pending_clarification,
                include_outside=False,
                provider=provider,
            )
        if isinstance(turn, FindTurnAsk):
            return replace(
                state,
                messages=(
                    *state.messages,
                    FindChatMessage(role="USER", text=text),
                    FindChatMessage(
                        role="MEM",
                        text=f"{turn.understanding}\n\n{turn.question}",
                    ),
                ),
                status="WAITING FOR CLARIFICATION · RESULTS UNCHANGED",
            )
        proposal = _show_result_proposal(state, turn, text)
        if proposal.result.kind == "artifact":
            return _apply_artifact_show_result(state, proposal)
        # The submitted natural-language turn is the authority for this proven
        # read-only action. Mutating actions will require a separate
        # exact-command approval rather than sharing this execution path.
        return _apply_show_result(state, proposal)

    def _visible_candidates(
        self,
        state: FindChatState,
    ) -> tuple[SearchCandidate, ...]:
        """Resolve the current visible aliases against the frozen frame."""
        visible: list[SearchCandidate] = []
        for result in state.results:
            candidates = [
                candidate
                for candidate in self.frame_candidates
                if candidate.context_name == result.context_name
                and candidate.item.uid == result.uid
            ]
            if len(candidates) != 1:
                raise FindError(
                    "The visible Find result no longer matches its evidence frame."
                )
            visible.append(candidates[0])
        return tuple(visible)

    def _refine(
        self,
        state: FindChatState,
        submitted_text: str,
        turn: FindTurnRefine,
        provider: FindAnswerProvider,
    ) -> FindChatState:
        """Replace visible results by reranking the same frozen frame."""
        matches = rank_candidates(
            turn.query,
            list(self.frame_candidates),
            provider,
            limit=self.limit,
        )
        related_query = _related_query_for_matches(matches)
        return replace(
            state,
            current_query=turn.query,
            messages=(
                *state.messages,
                FindChatMessage(role="USER", text=submitted_text),
                FindChatMessage(
                    role="MEM",
                    text=(
                        f"{turn.understanding}\n\n"
                        + _find_result_message(matches, refined=True)
                    ),
                ),
            ),
            results=tuple(
                _chat_result(match, index)
                for index, match in enumerate(matches, start=1)
            ),
            related_query=related_query,
            kept_count=0,
            status=_find_result_status(matches, refined=True),
            pending_answer=None,
        )

    def _handle_scope_confirmation(
        self,
        state: FindChatState,
        text: str,
    ) -> FindChatState:
        pending = state.pending_answer
        if pending is None:  # pragma: no cover - guarded by the caller
            raise FindError("Find has no pending wider-scope answer.")
        token = text.strip().casefold()
        if token == FIND_OUTSIDE_CANCELLATION:
            return replace(
                state,
                messages=(
                    *state.messages,
                    FindChatMessage(role="USER", text=text),
                    FindChatMessage(
                        role="MEM",
                        text="The other-Context answer request was cancelled.",
                    ),
                ),
                status="OTHER CONTEXTS CANCELLED · RESULTS UNCHANGED",
                pending_answer=None,
            )
        if token != FIND_OUTSIDE_CONFIRMATION:
            return replace(
                state,
                messages=(
                    *state.messages,
                    FindChatMessage(role="USER", text=text),
                    FindChatMessage(
                        role="MEM",
                        text=(
                            "The wider scope was not confirmed. Type exactly "
                            f"`{FIND_OUTSIDE_CONFIRMATION}` to continue, or "
                            f"`{FIND_OUTSIDE_CANCELLATION}` to cancel."
                        ),
                    ),
                ),
                status="WAITING FOR OTHER CONTEXTS CONFIRMATION",
            )
        provider = connect_codex_chatgpt_provider()
        return self._answer(
            state,
            submitted_text=text,
            answer_question=pending.user_text,
            interpreted_request=pending.interpreted_request,
            pending_clarification=pending.pending_clarification,
            include_outside=True,
            provider=provider,
        )

    def _answer(
        self,
        state: FindChatState,
        *,
        submitted_text: str,
        answer_question: str,
        interpreted_request: str,
        pending_clarification: str | None,
        include_outside: bool,
        provider: FindAnswerProvider,
    ) -> FindChatState:
        # The provider object has already passed the same runtime interface
        # check used by the dialogue adapters; keeping this method provider-
        # agnostic makes the two-turn confirmation path share one boundary.
        complete = getattr(provider, "complete", None)
        if not callable(complete):
            raise FindError("Find answer provider is not available.")
        if not state.results or any(
            result.relevance != "primary" for result in state.results
        ):
            # Related fallbacks aid discovery but are not evidence that the
            # original query was satisfied. A REFINE turn must promote them
            # through a fresh primary ranking before answer synthesis.
            raise FindError(
                "Related Find results cannot answer the original query. "
                "Refine the Find first."
            )
        visible_candidates = self._visible_candidates(state)
        visible = visible_result_evidence(visible_candidates)
        context = context_remainder_evidence(
            self.frame_candidates,
            visible_candidates,
        )
        outside = ()
        outside_status: FindOutsideStatus = "NOT_REQUESTED"
        if include_outside:
            collected = collect_outside_context_evidence(
                self.store,
                excluded_context_uids=frame_context_uids(
                    self.root_context,
                    recursive=self.recursive,
                    additional_roots=self.frame_roots[1:],
                ),
                excluded_candidates=self.frame_candidates,
            )
            outside = collected.evidence
            outside_status = collected.status
        try:
            answer = synthesize_find_answer(
                answer_question,
                visible,
                context,
                outside,
                outside_status,
                provider,
                interpreted_request=interpreted_request,
                pending_clarification=pending_clarification,
            )
        except FindAnswerCorpusTooLarge:
            if not include_outside:
                raise
            # A confirmed global scan can exceed the prototype corpus ceiling.
            # Preserve the same-Context answer and state that the outside scope
            # could not be completed instead of silently sampling a subset.
            outside = ()
            outside_status = "UNAVAILABLE"
            answer = synthesize_find_answer(
                answer_question,
                visible,
                context,
                outside,
                outside_status,
                provider,
                interpreted_request=interpreted_request,
                pending_clarification=pending_clarification,
            )
        rendered = render_find_answer_references(
            compact_artifact_references(
                (*visible, *context, *outside),
                self.frame_candidates,
            ),
            answer.sentences,
        )
        return replace(
            state,
            messages=(
                *state.messages,
                FindChatMessage(role="USER", text=submitted_text),
                FindChatMessage(role="MEM", text=rendered),
            ),
            status=_find_answer_status(outside_status),
            pending_answer=None,
        )


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _load_find_frame_roots(
    store: MemoryStore,
    root: Context,
    *,
    recursive: bool,
    resolve_embeds: bool,
) -> tuple[Context, ...]:
    """Freeze the selected Context plus every materialized namespace descendant."""
    if not recursive:
        return (root,)

    prefix = root.name + "/"
    load = store.load if resolve_embeds else store.load_direct
    roots = [root]
    seen_uids = {root.uid}
    # Namespace scope is determined once per Find. It is a provider boundary:
    # every ordinary Context below this canonical prefix may contribute content
    # to ranking, while query-only sources remain outside the ordinary catalog.
    for name in store.list_context_names():
        if not name.startswith(prefix):
            continue
        descendant = load(name)
        if descendant.uid in seen_uids:
            continue
        seen_uids.add(descendant.uid)
        roots.append(descendant)
    return tuple(roots)


def _collect_find_frame_candidates(
    store: MemoryStore,
    frame_roots: Sequence[Context],
    *,
    recursive: bool,
    include_artifacts: bool,
) -> tuple[SearchCandidate, ...]:
    """Freeze ordinary items and permitted profile-local activity evidence."""
    candidates = collect_candidates_from_roots(
        frame_roots,
        recursive=recursive,
    )
    if include_artifacts:
        candidates = append_artifact_candidates(
            candidates,
            collect_search_artifacts(store, frame_roots),
        )
    return tuple(candidates)


def _history_context_names(
    store: MemoryStore,
    roots: Sequence[Context],
    *,
    recursive: bool,
) -> tuple[str, ...]:
    """Collect histories from namespace roots and their embedded graphs."""
    names: list[str] = []
    visited: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited:
            return
        visited.add(context.uid)
        names.append(context.name)
        if not recursive:
            return
        for item in context.iter_items():
            if isinstance(item, Context) and store.context_exists(item.name):
                # Historical traversal follows only explicit embedded
                # Context pointers and uses non-resolving direct loads.
                # MemoryRef targets and query-only sources stay unopened.
                visit(store.load_direct(item.name))

    for root in roots:
        visit(root)
    return tuple(names)


def _temporal_find_results(
    store: MemoryStore,
    roots: Sequence[Context],
    query: str,
    *,
    recursive: bool,
    limit: int,
) -> list[HistorySearchResult]:
    timelines = [
        build_history(store, name)
        for name in _history_context_names(
            store,
            roots,
            recursive=recursive,
        )
    ]
    return search_history(
        timelines,
        query,
        connect_codex_chatgpt_provider(),
        result_kinds=(
            "memory_version",
            "memory_transition",
            "checkpoint",
        ),
        limit=limit,
    )


def _render_temporal_find(
    root_name: str,
    results: list[HistorySearchResult],
) -> None:
    if not results:
        typer.secho(display_escape_text(root_name), bold=True)
        typer.echo("  (no matching historical items)")
        return
    grouped: dict[tuple[str, str], list[HistorySearchResult]] = {}
    for result in results:
        grouped.setdefault(
            (result.context_uid, result.context_name),
            [],
        ).append(result)
    for group_index, ((_, context_name), matches) in enumerate(grouped.items()):
        if group_index:
            typer.echo()
        typer.secho(display_escape_text(context_name), bold=True)
        for result in matches:
            timestamp = (
                result.timestamp[:16].replace("T", " ")
                if result.timestamp
                else "current"
            )
            checkpoint = result.checkpoint_uid or result.candidate_id
            typer.echo(
                f"  [{result.kind:<17} {checkpoint[:8]}] "
                f"{display_escape_text(timestamp)}  "
                f"{display_escape_text(result.description)}  "
                f"({display_escape_text(history_result_recovery_label(result))})"
            )


def _render_labeled_content(label: str, content: str) -> None:
    """Render the first content line beside its item and align continuations."""
    lines = safe_terminal_text(content).splitlines() or [""]
    typer.echo(f"{label} {lines[0]}")
    continuation = " " * (len(label) + 1)
    for line in lines[1:]:
        typer.echo(f"{continuation}{line}")


def _render_match(match: SearchMatch) -> None:
    candidate = match.candidate
    item = candidate.item
    if isinstance(item, Memory):
        _render_labeled_content(
            (
                f"[related memory {item.uid[:8]}]"
                if match.relevance == "related"
                else f"[memory  {item.uid[:8]}]"
            ),
            item.content,
        )
    elif isinstance(item, MemoryRef):
        label = (
            (
                f"[related ref {item.uid[:8]}] "
                if match.relevance == "related"
                else f"[ref     {item.uid[:8]}] "
            )
            + f"-> {display_escape_text(item.target_context_name)}#"
            f"{display_escape_text(item.target_memory_uid[:8])}"
        )
        if item.target is not None:
            _render_labeled_content(label, item.target.content)
        else:
            typer.echo(label)
    elif isinstance(item, QueryContextRef):
        label = (
            f"[related query {item.uid[:8]}]"
            if match.relevance == "related"
            else f"[query   {item.uid[:8]}]"
        )
        typer.echo(f"{label} {display_escape_text(item.name)} (query-only)")
        command = shlex.join(
            [
                "mem",
                "query",
                item.name,
                "<question>",
                "--context",
                candidate.context_name,
            ]
        )
        typer.echo(f"{' ' * (len(label) + 1)}Ask with: {display_escape_text(command)}")
    elif isinstance(item, SearchArtifact):
        label = (
            f"[related {item.artifact_kind} {item.uid[:8]}]"
            if match.relevance == "related"
            else f"[{item.artifact_kind} {item.uid[:8]}]"
        )
        summary = item.summary.strip() or item.title
        _render_labeled_content(label, f"{item.title} · {summary}")


def _chat_result(match: SearchMatch, index: int) -> FindChatResult:
    candidate = match.candidate
    item = candidate.item
    if isinstance(item, Memory):
        content = item.content
    elif isinstance(item, MemoryRef):
        content = (
            item.target.content if item.target is not None else "(dangling reference)"
        )
    elif isinstance(item, QueryContextRef):
        content = f"{item.name} (query-only)"
    elif isinstance(item, SearchArtifact):
        content = f"{item.title}\n{item.content}"
    else:  # pragma: no cover - SearchMatch validates the result union
        raise FindError("Find returned an unsupported result type.")
    return FindChatResult(
        alias=f"m{index}",
        context_name=candidate.context_name,
        kind={
            "memory": "memory",
            "memory_ref": "ref",
            "query_context": "query",
            "artifact": "artifact",
        }[candidate.kind],
        uid=item.uid,
        content=content,
        relevance=match.relevance,
    )


def _related_query_for_matches(matches: Sequence[SearchMatch]) -> str:
    """Return one common related query while rejecting mixed local tiers."""
    related_queries = {
        match.related_query
        for match in matches
        if match.relevance == "related"
    }
    primary_count = sum(match.relevance == "primary" for match in matches)
    related_count = sum(match.relevance == "related" for match in matches)
    if primary_count and related_count:
        raise FindError("Find cannot mix primary and related results.")
    if related_count:
        if len(related_queries) != 1 or None in related_queries:
            raise FindError("Related Find results require one broader query.")
        return next(iter(related_queries)) or ""
    return ""


def _find_result_message(
    matches: Sequence[SearchMatch],
    *,
    refined: bool = False,
) -> str:
    related_query = _related_query_for_matches(matches)
    count = len(matches)
    noun = "Memory" if count == 1 else "Memories"
    suffix = " after refining the Find" if refined else ""
    if related_query:
        return (
            "I found no primary matches. "
            f"I am showing {count} related {noun}{suffix} for the broader "
            f"search: {related_query}."
        )
    return f"I found {count} matching {noun}{suffix}."


def _find_result_status(
    matches: Sequence[SearchMatch],
    *,
    refined: bool = False,
) -> str:
    related_query = _related_query_for_matches(matches)
    if related_query:
        status = "NO PRIMARY MATCHES · SHOWING RELATED RESULTS"
    elif matches:
        status = "RESULTS READY"
    else:
        status = "NO MATCHING RESULTS"
    return status + (" · REFINED" if refined else "")


def _initial_chat_state(
    context_name: str,
    query: str,
    matches: list[SearchMatch],
) -> FindChatState:
    related_query = _related_query_for_matches(matches)
    return FindChatState(
        context_name=context_name,
        current_query=query,
        messages=(
            FindChatMessage(role="USER", text=query),
            FindChatMessage(
                role="MEM",
                text=_find_result_message(matches),
            ),
        ),
        results=tuple(
            _chat_result(match, index) for index, match in enumerate(matches, start=1)
        ),
        related_query=related_query,
        status=_find_result_status(matches),
    )


def _show_result_proposal(
    state: FindChatState,
    action: FindTurnAction,
    submitted_text: str,
) -> FindShowProposal:
    matches = tuple(
        result for result in state.results if result.alias == action.selector
    )
    if len(matches) != 1:
        raise FindError("The requested Find result is missing or ambiguous.")
    selected = matches[0]
    review = ExactCommandReview(
        argv=(
            "mem",
            "show",
            selected.uid,
            "--context",
            selected.context_name,
        ),
        effects=(
            (
                f"Read-only inspection: SHOW {selected.alias} "
                f"from {selected.context_name}"
            ),
            "Contexts, Memories, checkpoints, and current Context: unchanged",
        ),
    )
    return FindShowProposal(
        action=action,
        result=selected,
        review=review,
        submitted_text=submitted_text,
    )


def _apply_artifact_show_result(
    state: FindChatState,
    proposal: FindShowProposal,
) -> FindChatState:
    """Inspect a frozen artifact without pretending it is an ordinary Memory."""
    action = proposal.action
    return replace(
        state,
        messages=(
            *state.messages,
            FindChatMessage(role="USER", text=proposal.submitted_text),
            FindChatMessage(
                role="MEM",
                text=(
                    f"{action.understanding}\n\n{action.question}\n\n"
                    f"{proposal.result.content}"
                ),
            ),
            FindChatMessage(
                role="STATUS",
                text="READ-ONLY ARTIFACT · SHOWN · Find results unchanged.",
            ),
        ),
        status=f"SHOWED {proposal.result.alias} · RESULTS UNCHANGED",
    )


def _run_read_only_find_command(
    argv: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    """Run one allowlisted read-only logical mem argv without a shell."""
    if (
        len(argv) != 5
        or argv[:2] != ("mem", "show")
        or argv[3] != "--context"
        or not argv[2]
        or not argv[4]
    ):
        raise FindError("Find refused a non-show follow-up command.")
    return subprocess.run(
        [sys.executable, "-m", "memcommit.cli", *argv[1:]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def _apply_show_result(
    state: FindChatState,
    proposal: FindShowProposal,
) -> FindChatState:
    try:
        completed = _run_read_only_find_command(proposal.review.argv)
    except subprocess.TimeoutExpired as error:
        raise FindError("The read-only mem show action timed out.") from error
    except OSError as error:
        raise FindError(
            "The read-only mem show action could not be started."
        ) from error
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise FindError(
            "The read-only mem show action failed" + (f": {detail}" if detail else ".")
        )
    actual_output = completed.stdout.strip()
    if not actual_output:
        raise FindError("The read-only mem show action returned no output.")
    action = proposal.action
    return replace(
        state,
        messages=(
            *state.messages,
            FindChatMessage(
                role="USER",
                text=proposal.submitted_text,
            ),
            FindChatMessage(
                role="MEM",
                text=f"{action.understanding}\n\n{action.question}",
            ),
            FindChatMessage(
                role="STATUS",
                text="\n".join(
                    [
                        "READ-ONLY ACTION · APPLIED",
                        f"  {format_exact_command(proposal.review)}",
                        "",
                        "ACTUAL OUTPUT",
                        actual_output,
                        "",
                        "Find results unchanged.",
                    ]
                ),
            ),
        ),
        status=f"SHOWED {proposal.result.alias} · RESULTS UNCHANGED",
    )


def _handle_find_turn(
    state: FindChatState,
    text: str,
) -> FindChatState:
    store = MemoryStore()
    access = resolve_context_access(
        store,
        state.context_name,
        current_name=store.current_context_name(),
        required_permission="READ",
    )
    read_store = GrantedReadStore(access) if access.is_granted else store
    root = read_store.load(access.display_name)
    frame_roots = _load_find_frame_roots(
        read_store,
        root,
        recursive=True,
        resolve_embeds=True,
    )
    frame_candidates = _collect_find_frame_candidates(
        store,
        frame_roots,
        recursive=True,
        include_artifacts=not access.is_granted,
    )
    return FindTurnController(
        store=read_store,
        root_context=root,
        frame_roots=frame_roots,
        recursive=True,
        limit=5,
        frame_candidates=frame_candidates,
    )(state, text)


def _run_interactive_find(
    store: MemoryStore,
    root_context: Context,
    frame_roots: tuple[Context, ...],
    query: str,
    matches: list[SearchMatch],
    *,
    recursive: bool,
    limit: int,
) -> FindChatSessionResult:
    frame_candidates = _collect_find_frame_candidates(
        store,
        frame_roots,
        recursive=recursive,
        include_artifacts=isinstance(store, MemoryStore),
    )
    controller = FindTurnController(
        store=store,
        root_context=root_context,
        frame_roots=frame_roots,
        recursive=recursive,
        limit=limit,
        frame_candidates=frame_candidates,
    )
    result = run_find_chat_session(
        _initial_chat_state(root_context.name, query, matches),
        handle_turn=controller,
    )
    typer.echo(
        f"Find dialogue closed with {len(result.state.results)} visible "
        f"result(s) after {len(result.submitted_turns)} follow-up turn(s)."
    )
    return result


def cmd(
    query: Annotated[
        str,
        typer.Argument(help="Natural-language query to find matching items"),
    ],
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to search (defaults to current)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum matches to return (1-20)",
        ),
    ] = 5,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            help=(
                "Search only direct items in the selected Context; exclude "
                "namespace descendants and embedded Contexts"
            ),
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        selected_name = context_snapshot.resolve_or_current(context_name)
        if selected_name is None:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        access = resolve_context_access(
            store,
            context_name,
            current_name=context_snapshot.current_name,
            required_permission="READ",
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    temporal = is_temporal_query(query)
    if not 1 <= limit <= 20:
        typer.secho(
            "Find error: Find limit must be between 1 and 20.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    try:
        if temporal and access.is_granted:
            raise RuntimeError(
                "Temporal Find is unavailable for a granted READ view because "
                "the grant does not expose authority checkpoint history."
            )
        read_store = GrantedReadStore(access) if access.is_granted else store
        if temporal:
            ctx = read_store.load_direct(access.display_name)
        else:
            ctx = read_store.load(access.display_name)
        frame_roots = _load_find_frame_roots(
            read_store,
            ctx,
            recursive=not direct,
            resolve_embeds=not temporal,
        )
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if temporal:
        try:
            history_results = _temporal_find_results(
                read_store,
                frame_roots,
                query,
                recursive=not direct,
                limit=limit,
            )
        except (
            HistoryError,
            HistorySearchError,
            QueryProviderError,
            OSError,
            RuntimeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Find history error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if _interactive_terminal() and history_results:
            try:
                choose_history(
                    history_result_picker_entries(history_results),
                    context_name=ctx.name,
                    mode="log",
                )
            except ValueError as error:
                typer.secho(
                    "Find history error: " + display_escape_text(str(error)),
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
            return
        _render_temporal_find(ctx.name, history_results)
        return

    try:
        frame_candidates = _collect_find_frame_candidates(
            store,
            frame_roots,
            recursive=not direct,
            include_artifacts=not access.is_granted,
        )
        provider = connect_codex_chatgpt_provider()
        matches = rank_candidates(
            query,
            list(frame_candidates),
            provider,
            limit=limit,
        )
    except (FindError, QueryProviderError) as error:
        typer.secho(
            f"Find error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if _interactive_terminal():
        _run_interactive_find(
            read_store,
            ctx,
            frame_roots,
            query,
            matches,
            recursive=not direct,
            limit=limit,
        )
        return

    if not matches:
        typer.secho(display_escape_text(ctx.name), bold=True)
        typer.echo("  (no matching items)")
        return

    related_query = _related_query_for_matches(matches)
    if related_query:
        typer.secho(display_escape_text(ctx.name), bold=True)
        typer.echo("  (no primary matches)")
        typer.echo()
        typer.secho("RELATED RESULTS", bold=True)
        typer.echo(
            "  Broader search: " + display_escape_text(related_query)
        )
        typer.echo("  Related items do not satisfy the original query.")

    # Grouping makes the owning Context legible without repeating it on every
    # row. Dict insertion order keeps the model's first Context appearance,
    # while each group's rows retain their relative ranking.
    grouped: dict[tuple[str, str], list[SearchMatch]] = {}
    for match in matches:
        owner = (
            match.candidate.context_uid,
            match.candidate.context_name,
        )
        grouped.setdefault(owner, []).append(match)

    for group_index, ((_, owner_name), owner_matches) in enumerate(grouped.items()):
        if group_index or related_query:
            typer.echo()
        typer.secho(display_escape_text(owner_name), bold=True)
        for match in owner_matches:
            _render_match(match)

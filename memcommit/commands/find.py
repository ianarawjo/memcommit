import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Annotated, Optional

import typer

from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    context_access_display_facts,
    resolve_context_access,
)
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
from memcommit.commands.find_search_workbench import (
    FindSearchRequest,
    FindSearchResponse,
    FindSearchResult,
    run_find_search_workbench,
)
from memcommit.commands.find_materialization import (
    FindMaterializationError,
    materialize_find_results,
)
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.history_picker import choose_history
from memcommit.commands.history_present import (
    history_result_recovery_label,
    history_result_picker_entries,
)
from memcommit.commands.readable_context_catalog import (
    ReadableContextCatalog,
    freeze_readable_context_catalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.context_targeting.search import (
    collect_readable_search_candidates,
    load_readable_search_roots,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.commands.search_result_present import group_search_items
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
    rank_candidates,
)
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceState,
)
from memcommit.source_projection.presentation import (
    source_annotation_text,
    source_object_label,
)
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
        if self.recursive:
            matches = _supplement_namespace_branch_coverage(
                turn.query,
                self.frame_candidates,
                matches,
                provider,
                root_name=self.root_context.name,
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
    """Compatibility adapter for the former Find-owned scope helper."""

    return load_readable_search_roots(
        store,
        (root.name,),
        include_descendants=recursive,
        follow_embeds=resolve_embeds,
    )


def _load_find_scope_roots(
    store: ReadableContextCatalog,
    target_names: Sequence[str],
    *,
    include_descendants: bool,
    follow_embeds: bool,
) -> tuple[Context, ...]:
    """Compatibility adapter for tests and retained Find callers."""

    return load_readable_search_roots(
        store,
        target_names,
        include_descendants=include_descendants,
        follow_embeds=follow_embeds,
    )


def _collect_find_frame_candidates(
    store: MemoryStore,
    frame_roots: Sequence[Context],
    *,
    recursive: bool,
    include_artifacts: bool,
) -> tuple[SearchCandidate, ...]:
    """Compatibility adapter for the shared ordinary searchable corpus."""

    return collect_readable_search_candidates(
        store,
        frame_roots,
        follow_embeds=recursive,
        artifact_roots=frame_roots if include_artifacts else (),
    )


def _namespace_branch(name: str, root_name: str) -> str | None:
    """Return the first canonical namespace segment below one Find root."""

    prefix = root_name + "/"
    if not name.startswith(prefix):
        return None
    return name[len(prefix) :].split("/", 1)[0]


def _supplement_namespace_branch_coverage(
    query: str,
    candidates: Sequence[SearchCandidate],
    matches: list[SearchMatch],
    provider,
    *,
    root_name: str,
    limit: int,
) -> list[SearchMatch]:
    """Preserve a material match from another relevant public branch.

    Global semantic ranking can fill a small limit with near-duplicate facts
    from one branch. A second bounded rank over omitted sibling branches asks
    the same primary-relevance question; it does not force an irrelevant
    branch into the result.
    """

    if (
        limit < 2
        or not matches
        or any(match.relevance != "primary" for match in matches)
    ):
        return matches
    candidate_branches = {
        branch
        for candidate in candidates
        if candidate.kind != "artifact"
        if (branch := _namespace_branch(candidate.context_name, root_name)) is not None
    }
    selected_branches = {
        branch
        for match in matches
        if (
            branch := _namespace_branch(
                match.candidate.context_name,
                root_name,
            )
        )
        is not None
    }
    omitted = candidate_branches - selected_branches
    if not selected_branches or not omitted:
        return matches
    omitted_candidates = [
        candidate
        for candidate in candidates
        if _namespace_branch(candidate.context_name, root_name) in omitted
        and candidate.kind != "artifact"
    ]
    supplemental = [
        match
        for match in rank_candidates(
            query,
            omitted_candidates,
            provider,
            limit=limit,
        )
        if match.relevance == "primary"
    ]
    if not supplemental:
        return matches

    reserve = min(len(supplemental), max(1, min(3, limit // 2)))
    keep = min(len(matches), limit - reserve)
    combined = [*matches[:keep], *supplemental[:reserve]]
    seen: set[tuple[str, str]] = set()
    result: list[SearchMatch] = []
    for match in combined:
        identity = (match.candidate.context_uid, match.candidate.item.uid)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(match)
    return result[:limit]


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
    with CommandProgress(
        "FIND HISTORY",
        "connecting provider",
        total=2,
    ) as progress:
        provider = connect_codex_chatgpt_provider()
        progress.update("searching history", step=2)
        return search_history(
            timelines,
            query,
            provider,
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
        item_label = source_object_label(SourceForm.MEMORY)
        relevance = " · RELATED" if match.relevance == "related" else ""
        _render_labeled_content(
            f"[{item_label} {item.uid[:8]}]{relevance}",
            item.content,
        )
    elif isinstance(item, MemoryRef):
        facts = SourceDisplayFacts(
            form=SourceForm.MEMORY_REF,
            states=(
                (SourceState.READ_ONLY,)
                if item.target is not None
                else (SourceState.DANGLING,)
            ),
        )
        item_label = source_object_label(facts)
        annotations = [
            *(("RELATED",) if match.relevance == "related" else ()),
            source_annotation_text(facts),
        ]
        annotation = " · ".join(value for value in annotations if value)
        label = (
            f"[{item_label} {item.uid[:8]}]"
            + (f" · {annotation}" if annotation else "")
            + " "
            + f"-> {display_escape_text(item.target_context_name)}#"
            f"{display_escape_text(item.target_memory_uid[:8])}"
        )
        if item.target is not None:
            _render_labeled_content(label, item.target.content)
        else:
            typer.echo(label)
    elif isinstance(item, QueryContextRef):
        item_label = source_object_label(SourceForm.QUERY_VIEW)
        relevance = " · RELATED" if match.relevance == "related" else ""
        label = f"[{item_label} {item.uid[:8]}]{relevance}"
        typer.echo(f"{label} {display_escape_text(item.name)}")
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
        facts = SourceDisplayFacts(
            form=SourceForm.MEMORY_REF,
            states=(SourceState.DANGLING,),
        )
        content = (
            item.target.content
            if item.target is not None
            else f"({source_annotation_text(facts)} memory ref)"
        )
    elif isinstance(item, QueryContextRef):
        content = f"{item.name} · {source_object_label(SourceForm.QUERY_VIEW)}"
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
        match.related_query for match in matches if match.relevance == "related"
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
    read_store = freeze_readable_context_catalog(store, access)
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
        # Other-Context confirmation retains its established profile-local
        # boundary; the unified catalog is only the selected Find frame.
        store=store,
        root_context=root,
        frame_roots=frame_roots,
        recursive=True,
        limit=5,
        frame_candidates=frame_candidates,
    )(state, text)


def _run_interactive_find(
    store: MemoryStore,
    outside_store: MemoryStore,
    root_context: Context,
    frame_roots: tuple[Context, ...],
    query: str,
    matches: list[SearchMatch],
    *,
    recursive: bool,
    limit: int,
    frame_candidates: tuple[SearchCandidate, ...],
) -> FindChatSessionResult:
    controller = FindTurnController(
        store=outside_store,
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


def _find_search_result(
    match: SearchMatch,
    index: int,
) -> FindSearchResult:
    rendered = _chat_result(match, index)
    candidate = match.candidate
    item = candidate.item
    if isinstance(item, Memory):
        source_identity = (
            candidate.context_name,
            candidate.context_uid,
            item.uid,
        )
    elif isinstance(item, MemoryRef):
        source_identity = (
            item.target_context_name,
            item.target_context_uid,
            item.target_memory_uid,
        )
    else:
        source_identity = (None, None, None)
    return FindSearchResult(
        context_name=rendered.context_name,
        kind=rendered.kind,
        uid=rendered.uid,
        content=rendered.content,
        relevance=rendered.relevance,
        source_context_name=source_identity[0],
        source_context_uid=source_identity[1],
        source_memory_uid=source_identity[2],
    )


def _history_find_search_result(
    result: HistorySearchResult,
) -> FindSearchResult:
    timestamp = (
        result.timestamp[:16].replace("T", " ") if result.timestamp else "current"
    )
    return FindSearchResult(
        context_name=result.context_name,
        kind=result.kind,
        uid=result.checkpoint_uid or result.candidate_id,
        content=(
            f"{timestamp} · {result.description} · "
            f"{history_result_recovery_label(result)}"
        ),
    )


def _run_find_search_request(
    store: MemoryStore,
    catalog: ReadableContextCatalog,
    request: FindSearchRequest,
) -> FindSearchResponse:
    """Execute one frozen interactive request without mutating the workbench."""

    roots = _load_find_scope_roots(
        catalog,
        request.target_names,
        include_descendants=request.include_descendants,
        follow_embeds=request.follow_embeds,
    )
    temporal = is_temporal_query(request.query)
    if temporal:
        history_names = _history_context_names(
            catalog,
            roots,
            recursive=request.follow_embeds,
        )
        if any(catalog.access_for(name).is_granted for name in history_names):
            raise RuntimeError(
                "Temporal Find is unavailable for a granted READ view because "
                "the grant does not expose authority checkpoint history."
            )
        timelines = [build_history(store, name) for name in history_names]
        provider = connect_codex_chatgpt_provider()
        history_results = search_history(
            timelines,
            request.query,
            provider,
            result_kinds=(
                "memory_version",
                "memory_transition",
                "checkpoint",
            ),
            limit=request.limit,
        )
        return FindSearchResponse(
            request=request,
            mode="HISTORY",
            results=tuple(
                _history_find_search_result(result) for result in history_results
            ),
        )

    # Activity evidence belongs to the active Profile. READ-granted roots can
    # contribute their authorized Memories, but never the authority Profile's
    # private checkpoints, sessions, traces, or rationale records.
    local_roots: list[Context] = []
    for root in roots:
        try:
            access = catalog.access_for(root.name)
        except FileNotFoundError:
            continue
        if not access.is_granted:
            local_roots.append(root)
    candidates = collect_readable_search_candidates(
        store,
        roots,
        follow_embeds=request.follow_embeds,
        artifact_roots=local_roots,
    )
    provider = connect_codex_chatgpt_provider()
    matches = rank_candidates(
        request.query,
        candidates,
        provider,
        limit=request.limit,
    )
    if len(request.target_names) == 1 and request.include_descendants:
        matches = _supplement_namespace_branch_coverage(
            request.query,
            candidates,
            matches,
            provider,
            root_name=request.target_names[0],
            limit=request.limit,
        )
    return FindSearchResponse(
        request=request,
        mode="CURRENT",
        results=tuple(
            _find_search_result(match, index)
            for index, match in enumerate(matches, start=1)
        ),
        related_query=_related_query_for_matches(matches),
    )


def _open_find_search_workbench(
    store: MemoryStore,
    access: ContextAccess,
    *,
    current_name: str | None,
    initial_targets: Sequence[str] = (),
    include_descendants: bool,
    follow_embeds: bool,
    limit: int,
) -> None:
    """Open a blank, query-focused Find over one frozen readable catalog."""

    catalog = freeze_profile_readable_context_catalog(
        store,
        access,
        include_query_routes=True,
    )
    names = tuple(catalog.list_context_names())
    initial_target = access.display_name
    if initial_target not in names:
        raise RuntimeError("The selected Context is outside the readable catalog.")
    displayed_current = current_name if current_name in names else initial_target
    granted_names = frozenset(
        name for name in names if catalog.access_for(name).is_granted
    )
    annotations = {
        name: context_access_display_facts(catalog.access_for(name))
        for name in granted_names
    }
    workbench_result = run_find_search_workbench(
        names,
        current=displayed_current,
        initial_target=initial_target,
        initial_targets=initial_targets or (initial_target,),
        initial_include_descendants=include_descendants,
        initial_follow_embeds=follow_embeds,
        limit=limit,
        run_search=lambda request: _run_find_search_request(
            store,
            catalog,
            request,
        ),
        annotations=annotations,
        granted_context_names=granted_names,
        local_context_names=tuple(store.list_context_names()),
        validate_save_location=store.assert_context_creatable,
    )
    # Compatibility capture stubs used by read-only callers historically
    # returned None; only the typed MATERIALIZE result crosses the write edge.
    if workbench_result is None or workbench_result.status != "MATERIALIZE":
        return
    assert workbench_result.response is not None
    assert workbench_result.materialize_as is not None
    assert workbench_result.save_location is not None
    materialized = materialize_find_results(
        store,
        catalog,
        workbench_result.response,
        selected_result_indices=workbench_result.selected_result_indices,
        mode=workbench_result.materialize_as,
        destination_name=workbench_result.save_location,
    )
    typer.secho(
        f"Saved {len(materialized.item_uids)} checked Find result(s) as "
        f"{materialized.mode} in new Context "
        f"'{display_escape_text(materialized.context_name)}' "
        f"[{materialized.context_uid[:8]}]; sources unchanged.",
        fg=typer.colors.GREEN,
    )


def cmd(
    query: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help=(
                "Natural-language query; omit in a terminal to open the "
                "interactive search with Profile-wide or Context targets, "
                "Context range, embedded-Context scope, and checked-result "
                "COPY/REFERENCE Save As"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[list[str]],
        typer.Option(
            "--context",
            "-c",
            show_default=False,
            help=(
                "Context root to search; repeat for multiple roots "
                "(defaults to current)"
            ),
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
    include_descendants: Annotated[
        bool,
        typer.Option(
            "--descendants/--context-only",
            help=(
                "Include each selected Context root's readable lexical "
                "descendants, independently of embedded Context traversal"
            ),
        ),
    ] = True,
    follow_embeds: Annotated[
        bool,
        typer.Option(
            "--follow-embeds/--exclude-embeds",
            help=(
                "Follow embedded Context links from the selected lexical "
                "scope, independently of descendant expansion"
            ),
        ),
    ] = True,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            help=(
                "Compatibility shorthand for --context-only --exclude-embeds; "
                "takes precedence over the separate scope flags"
            ),
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    # Keep the established --direct script contract while exposing the same
    # independent lexical and embedded axes as the interactive Scope control.
    if direct:
        include_descendants = False
        follow_embeds = False
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        operands: tuple[str | None, ...] = (
            (context_name,)
            if isinstance(context_name, str)
            else tuple(context_name)
            if context_name
            else (None,)
        )
        accesses = tuple(
            resolve_context_access(
                store,
                operand,
                current_name=context_snapshot.current_name,
                required_permission="READ",
            )
            for operand in operands
        )
        target_names = tuple(access.display_name for access in accesses)
        if len(set(target_names)) != len(target_names):
            raise ValueError("Find Context roots must be distinct.")
        access = accesses[0]
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

    if not 1 <= limit <= 20:
        typer.secho(
            "Find error: Find limit must be between 1 and 20.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if query is None:
        if not _interactive_terminal():
            typer.secho(
                "Find error: QUERY is required outside a terminal. In a "
                "terminal, run 'mem find' to open the interactive search.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            workbench_options = {
                "current_name": context_snapshot.current_name,
                "include_descendants": include_descendants,
                "follow_embeds": follow_embeds,
                "limit": limit,
            }
            if len(target_names) > 1:
                workbench_options["initial_targets"] = target_names
            _open_find_search_workbench(store, access, **workbench_options)
        except (
            FindMaterializationError,
            FindError,
            HistoryError,
            HistorySearchError,
            QueryProviderError,
            FileNotFoundError,
            OSError,
            RuntimeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Find error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        return

    if len(target_names) > 1:
        try:
            catalog = freeze_profile_readable_context_catalog(
                store,
                access,
                include_query_routes=follow_embeds,
            )
            for target_access in accesses:
                catalog.access_for(target_access.display_name)
            response = _run_find_search_request(
                store,
                catalog,
                FindSearchRequest(
                    query=query,
                    target_names=target_names,
                    include_descendants=include_descendants,
                    follow_embeds=follow_embeds,
                    limit=limit,
                ),
            )
        except (
            FindError,
            HistoryError,
            HistorySearchError,
            QueryProviderError,
            FileNotFoundError,
            OSError,
            RuntimeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Find error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if not response.results:
            typer.secho(
                " + ".join(display_escape_text(name) for name in target_names),
                bold=True,
            )
            typer.echo(
                "  (no matching historical items)"
                if response.mode == "HISTORY"
                else "  (no matching items)"
            )
            return
        if response.related_query:
            typer.secho("RELATED RESULTS", bold=True)
            typer.echo(
                "  Broader search: "
                + display_escape_text(response.related_query)
            )
            typer.echo("  Related items do not satisfy the original query.")
            typer.echo()
        grouped: dict[str, list[FindSearchResult]] = {}
        for result in response.results:
            grouped.setdefault(result.context_name, []).append(result)
        for group_index, (owner_name, results) in enumerate(grouped.items()):
            if group_index:
                typer.echo()
            typer.secho(display_escape_text(owner_name), bold=True)
            for result in results:
                related = " · RELATED" if result.relevance == "related" else ""
                _render_labeled_content(
                    f"[{result.kind} {result.uid[:8]}]{related}",
                    result.content,
                )
        return

    temporal = is_temporal_query(query)
    try:
        if temporal and access.is_granted:
            raise RuntimeError(
                "Temporal Find is unavailable for a granted READ view because "
                "the grant does not expose authority checkpoint history."
            )
        if temporal:
            read_store = GrantedReadStore(access) if access.is_granted else store
            ctx = read_store.load_direct(access.display_name)
        else:
            read_store = freeze_readable_context_catalog(
                store,
                access,
                include_query_routes=follow_embeds,
            )
            ctx = (
                read_store.load(access.display_name)
                if follow_embeds
                else read_store.load_direct(access.display_name)
            )
        frame_roots = _load_find_frame_roots(
            read_store,
            ctx,
            recursive=include_descendants,
            resolve_embeds=follow_embeds and not temporal,
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
                recursive=follow_embeds,
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
            recursive=follow_embeds,
            include_artifacts=not access.is_granted,
        )
        with CommandProgress(
            "FIND",
            "connecting provider",
            total=3,
        ) as progress:
            provider = connect_codex_chatgpt_provider()
            progress.update("ranking candidates", step=2)
            matches = rank_candidates(
                query,
                list(frame_candidates),
                provider,
                limit=limit,
            )
            if include_descendants:
                progress.update("checking namespace coverage", step=3)
                matches = _supplement_namespace_branch_coverage(
                    query,
                    frame_candidates,
                    matches,
                    provider,
                    root_name=ctx.name,
                    limit=limit,
                )
    except (FindError, QueryProviderError) as error:
        typer.secho(
            f"Find error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

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
        typer.echo("  Broader search: " + display_escape_text(related_query))
        typer.echo("  Related items do not satisfy the original query.")

    groups = group_search_items(
        matches,
        context_name=lambda match: match.candidate.context_name,
    )
    for group_index, (owner_name, owner_matches) in enumerate(groups):
        if group_index or related_query:
            typer.echo()
        typer.secho(display_escape_text(owner_name), bold=True)
        for match in owner_matches:
            _render_match(match)

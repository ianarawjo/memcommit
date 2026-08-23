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
    run_find_search_workbench,
)
from memcommit.find_materialization_application import (
    FindMaterializationError,
    FindMaterializationRequest,
)
from memcommit.find_materialization_runtime import (
    execute_find_materialization,
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
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.derived_policy import authorize_combination
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
from memcommit.find_application import (
    FindSearchRequest,
    FindSearchResponse,
    FindSearchStage,
)
from memcommit.find_runtime import execute_find_search
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
from memcommit.infrastructure.providers.find_query import (
    connect_find_provider as connect_codex_chatgpt_provider,
)
from memcommit.history import HistoryError
from memcommit.history_search import (
    HistorySearchError,
    HistorySearchResult,
    is_temporal_query,
)
from memcommit.query_provider import QueryProviderError
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
    if state.status != "WAITING FOR CLARIFICATION":
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
                status="WAITING FOR CLARIFICATION",
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
                status="OTHER CONTEXTS CANCELLED",
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
        include_attached_reads=False,
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
            f"Show {selected.alias} from {selected.context_name}.",
            "This opens the selected result without editing stored data.",
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
                text="ARTIFACT SHOWN",
            ),
        ),
        status=f"SHOWED {proposal.result.alias}",
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
        raise FindError("The mem show action timed out.") from error
    except OSError as error:
        raise FindError(
            "The mem show action could not be started."
        ) from error
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise FindError(
            "The mem show action failed" + (f": {detail}" if detail else ".")
        )
    actual_output = completed.stdout.strip()
    if not actual_output:
        raise FindError("The mem show action returned no output.")
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
                        "RESULT SHOWN",
                        f"  {format_exact_command(proposal.review)}",
                        "",
                        "ACTUAL OUTPUT",
                        actual_output,
                        "",
                        "Stored data was not edited.",
                    ]
                ),
            ),
        ),
        status=f"SHOWED {proposal.result.alias}",
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
        f"Search dialogue closed with {len(result.state.results)} visible "
        f"result(s) after {len(result.submitted_turns)} follow-up turn(s)."
    )
    return result


def _run_find_search_request(
    store: MemoryStore,
    catalog: ReadableContextCatalog,
    request: FindSearchRequest,
    *,
    observer=None,
) -> FindSearchResponse:
    """Compatibility adapter over the terminal-independent Find runtime."""

    return execute_find_search(
        request,
        store=store,
        catalog=catalog,
        provider_factory=connect_codex_chatgpt_provider,
        observer=observer,
    )


def _render_find_search_response(
    response: FindSearchResponse,
    *,
    target_names: tuple[str, ...],
    all_readable_contexts: bool = False,
) -> None:
    """Present one typed application result without rerunning its search."""

    heading = (
        "ALL READABLE CONTEXTS"
        if all_readable_contexts
        else " + ".join(display_escape_text(name) for name in target_names)
    )
    if response.mode == "HISTORY":
        history_results = tuple(
            result.history_result
            for result in response.results
            if result.history_result is not None
        )
        if len(history_results) == len(response.results):
            if _interactive_terminal() and len(target_names) == 1 and history_results:
                choose_history(
                    history_result_picker_entries(history_results),
                    context_name=target_names[0],
                    mode="log",
                )
                return
            _render_temporal_find(heading, list(history_results))
            return

    if not response.results:
        typer.secho(heading, bold=True)
        typer.echo(
            "  (no matching historical items)"
            if response.mode == "HISTORY"
            else "  (no matching items)"
        )
        return
    if response.related_query:
        if len(target_names) == 1:
            typer.secho(heading, bold=True)
            typer.echo("  (no primary matches)")
            typer.echo()
        typer.secho("RELATED RESULTS", bold=True)
        typer.echo(
            "  No matching results for: "
            + display_escape_text(response.request.query)
        )
        typer.echo(
            "  Broader search: " + display_escape_text(response.related_query)
        )
        typer.echo()
    groups = group_search_items(
        response.results,
        context_name=lambda result: result.context_name,
    )
    for group_index, (owner_name, results) in enumerate(groups):
        if group_index or response.related_query:
            typer.echo()
        typer.secho(display_escape_text(owner_name), bold=True)
        for result in results:
            if result.current_match is not None:
                _render_match(result.current_match)
                continue
            related = " · RELATED" if result.relevance == "related" else ""
            _render_labeled_content(
                f"[{result.kind} {result.uid[:8]}]{related}",
                result.content,
            )
    if response.related_query:
        typer.echo()
        typer.echo("Related results may not satisfy the original query.")


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
    materialized = execute_find_materialization(
        FindMaterializationRequest(
            response=workbench_result.response,
            selected_result_indices=workbench_result.selected_result_indices,
            mode=workbench_result.materialize_as,
            destination_name=workbench_result.save_location,
        ),
        store=store,
        catalog=catalog,
    )
    typer.secho(
        f"Saved {len(materialized.item_uids)} checked Search result(s) as "
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
                "interactive search with compact exact-Context Scope, "
                "Browse-only Profile/multiple selection, independent range "
                "and Embed choices, and checked-result COPY/REFERENCE Save As"
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
    all_contexts: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Search all readable Contexts in the active Profile",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum matches to return (1-20)",
        ),
    ] = 5,
    include_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--descendants/--context-only",
            help=(
                "Include each selected Context root's readable lexical "
                "descendants, independently of embedded Context traversal"
            ),
        ),
    ] = None,
    follow_embeds: Annotated[
        Optional[bool],
        typer.Option(
            "--follow-embeds/--exclude-embeds",
            help=(
                "Follow embedded Context links from the selected lexical "
                "scope, independently of descendant expansion"
            ),
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Search only the selected Context roots",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants and follow embedded Contexts",
        ),
    ] = False,
) -> None:
    scope_flags_supplied = (
        direct
        or recursive
        or include_descendants is not None
        or follow_embeds is not None
    )
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=(
                ContextScopePreset.RECURSIVE
                if query is None and not scope_flags_supplied
                else ContextScopePreset.DIRECT
            ),
        )
        traversal = resolve_context_traversal(
            preset=preset,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
        )
        include_descendants = traversal.include_descendants
        follow_embeds = traversal.follow_embeds
    except (TypeError, ValueError) as error:
        typer.secho(
            f"Search error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore()
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        if all_contexts and context_name:
            raise ValueError("--all/-a cannot be combined with --context/-c.")
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
        all_readable_catalog = None
        if all_contexts:
            # PROFILE is a process-local shortcut, never a storage locator.
            # Freeze its concrete names once so later scope and provider work
            # cannot reinterpret --all after current/Profile state changes.
            all_readable_catalog = freeze_profile_readable_context_catalog(
                store,
                access,
                include_query_routes=follow_embeds,
            )
            target_names = tuple(all_readable_catalog.list_context_names())
            accesses = tuple(
                all_readable_catalog.access_for(name) for name in target_names
            )
            # Semantic retrieval combines every frozen contributor in one
            # provider frame, so READ visibility alone is insufficient for
            # granted Sources even though literal Find needs only READ.
            authorize_combination(accesses)
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
            "Search error: Search limit must be between 1 and 20.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if query is None:
        if not _interactive_terminal():
            typer.secho(
                "Search error: QUERY is required outside a terminal. In a "
                "terminal, run 'mem search' to open the interactive search.",
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
                f"Search error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        return

    request = FindSearchRequest(
        query=query,
        target_names=target_names,
        include_descendants=include_descendants,
        follow_embeds=follow_embeds,
        limit=limit,
    )
    temporal_query = is_temporal_query(query)
    try:
        if all_readable_catalog is not None or len(target_names) > 1:
            catalog = all_readable_catalog
            if catalog is None:
                catalog = freeze_profile_readable_context_catalog(
                    store,
                    access,
                    include_query_routes=follow_embeds,
                )
            for target_access in accesses:
                catalog.access_for(target_access.display_name)
            response = _run_find_search_request(store, catalog, request)
        else:
            catalog = freeze_readable_context_catalog(
                store,
                access,
                include_query_routes=follow_embeds,
            )
            with CommandProgress(
                "SEARCH HISTORY" if temporal_query else "SEARCH",
                "connecting provider",
                total=2 if temporal_query else 3,
            ) as progress:

                def observe(stage: FindSearchStage) -> None:
                    if stage == "SEARCHING":
                        progress.update(
                            (
                                "searching history"
                                if temporal_query
                                else "ranking candidates"
                            ),
                            step=2,
                        )
                    elif stage == "CHECKING_COVERAGE":
                        progress.update("checking namespace coverage", step=3)

                response = _run_find_search_request(
                    store,
                    catalog,
                    request,
                    observer=observe,
                )
        _render_find_search_response(
            response,
            target_names=target_names,
            all_readable_contexts=all_contexts,
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
        error_label = (
            "Search history error"
            if len(target_names) == 1 and temporal_query
            else "Search error"
        )
        typer.secho(
            f"{error_label}: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

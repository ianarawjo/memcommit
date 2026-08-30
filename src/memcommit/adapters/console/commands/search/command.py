import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.adapters.console.terminal.components.command_editor.model import CommandReview
from memcommit.adapters.console.terminal.components.command_editor.rendering import (
    format_exact_command,
)
from memcommit.adapters.console.commands.search.chat_shell import (
    SearchChatMessage,
    SearchChatResult,
    SearchChatSessionResult,
    SearchChatState,
    SearchPendingAnswerRequest,
    run_search_chat_session,
)
from memcommit.adapters.console.commands.search.search_workbench import (
    run_search_workbench,
)
from memcommit.application.operations.search.materialization_application import (
    SearchMaterializationError,
    SearchMaterializationRequest,
)
from memcommit.application.operations.search.materialization_runtime import (
    execute_search_materialization,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.application.capabilities.authority.readable_contexts import (
    ReadableContextCatalog,
    freeze_readable_context_catalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.application.operations.search.corpus import (
    collect_readable_search_candidates,
    load_readable_search_roots,
)
from memcommit.core.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.application.capabilities.authority.source_use_policy import authorize_combination
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.adapters.console.commands.search.result_present import group_search_items
from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.search.answer_dialogue import (
    SearchAnswerCorpusTooLarge,
    SearchAnswerProvider,
    SearchOutsideStatus,
    synthesize_search_answer,
)
from memcommit.application.operations.search.answer_references import (
    render_search_answer_references,
)
from memcommit.application.operations.search.application import (
    SearchRequest,
    SearchResponse,
    SearchStage,
)
from memcommit.application.operations.search.runtime import execute_search
from memcommit.application.operations.search.scope_evidence import (
    collect_outside_context_evidence,
    compact_artifact_references,
    context_remainder_evidence,
    frame_context_uids,
    visible_result_evidence,
)
from memcommit.application.operations.search.turn_dialogue import (
    SearchTurnAction,
    SearchTurnAnswer,
    SearchTurnAsk,
    SearchTurnRefine,
    interpret_search_turn,
)
from memcommit.providers.operation_connections import connect_search_provider
from memcommit.providers.subscription import QueryProviderError
from memcommit.application.operations.search.model import (
    SearchError,
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
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError


SEARCH_OUTSIDE_CONFIRMATION = "confirm other contexts"
SEARCH_OUTSIDE_CANCELLATION = "cancel other contexts"


def _outside_confirmation_message(user_text: str) -> str:
    korean = any("\uac00" <= character <= "\ud7a3" for character in user_text)
    if korean:
        return (
            "다른 저장 Context를 확인하면 그 안의 일반 Memory 내용도 "
            "이 답변을 만드는 provider에 전송됩니다.\n\n"
            f"계속하려면 정확히 `{SEARCH_OUTSIDE_CONFIRMATION}`를, "
            f"취소하려면 `{SEARCH_OUTSIDE_CANCELLATION}`를 입력하세요."
        )
    return (
        "Checking other stored Contexts will also send their ordinary Memory "
        "contents to the answer provider.\n\n"
        f"Type exactly `{SEARCH_OUTSIDE_CONFIRMATION}` to continue, or "
        f"`{SEARCH_OUTSIDE_CANCELLATION}` to cancel."
    )


def _pending_search_clarification(state: SearchChatState) -> str | None:
    if state.status != "WAITING FOR CLARIFICATION":
        return None
    return next(
        (message.text for message in reversed(state.messages) if message.role == "MEM"),
        None,
    )


@dataclass(frozen=True)
class SearchShowProposal:
    """One locally resolved read-only command for a visible Search result."""

    action: SearchTurnAction
    result: SearchChatResult
    review: CommandReview
    submitted_text: str


def _search_answer_status(outside_status: SearchOutsideStatus) -> str:
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
class SearchTurnController:
    """Frozen local evidence frame and provider orchestration for one Search."""

    store: MemoryStore
    root_context: Context
    frame_roots: tuple[Context, ...]
    recursive: bool
    limit: int
    frame_candidates: tuple[SearchCandidate, ...]

    def __call__(
        self,
        state: SearchChatState,
        text: str,
    ) -> SearchChatState:
        self._visible_candidates(state)
        if state.pending_answer is not None:
            return self._handle_scope_confirmation(state, text)
        provider = connect_search_provider()
        turn = interpret_search_turn(state, text, provider)
        if isinstance(turn, SearchTurnRefine):
            return self._refine(state, text, turn, provider)
        if isinstance(turn, SearchTurnAnswer):
            pending_clarification = _pending_search_clarification(state)
            if turn.scope == "ALL_CONTEXTS":
                return replace(
                    state,
                    messages=(
                        *state.messages,
                        SearchChatMessage(role="USER", text=text),
                        SearchChatMessage(
                            role="MEM",
                            text=_outside_confirmation_message(text),
                        ),
                    ),
                    status="WAITING FOR OTHER CONTEXTS CONFIRMATION",
                    pending_answer=SearchPendingAnswerRequest(
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
        if isinstance(turn, SearchTurnAsk):
            return replace(
                state,
                messages=(
                    *state.messages,
                    SearchChatMessage(role="USER", text=text),
                    SearchChatMessage(
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
        state: SearchChatState,
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
                raise SearchError(
                    "The visible Search result no longer matches its evidence frame."
                )
            visible.append(candidates[0])
        return tuple(visible)

    def _refine(
        self,
        state: SearchChatState,
        submitted_text: str,
        turn: SearchTurnRefine,
        provider: SearchAnswerProvider,
    ) -> SearchChatState:
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
                SearchChatMessage(role="USER", text=submitted_text),
                SearchChatMessage(
                    role="MEM",
                    text=(
                        f"{turn.understanding}\n\n"
                        + _search_result_message(matches, refined=True)
                    ),
                ),
            ),
            results=tuple(
                _chat_result(match, index)
                for index, match in enumerate(matches, start=1)
            ),
            related_query=related_query,
            kept_count=0,
            status=_search_result_status(matches, refined=True),
            pending_answer=None,
        )

    def _handle_scope_confirmation(
        self,
        state: SearchChatState,
        text: str,
    ) -> SearchChatState:
        pending = state.pending_answer
        if pending is None:  # pragma: no cover - guarded by the caller
            raise SearchError("Search has no pending wider-scope answer.")
        token = text.strip().casefold()
        if token == SEARCH_OUTSIDE_CANCELLATION:
            return replace(
                state,
                messages=(
                    *state.messages,
                    SearchChatMessage(role="USER", text=text),
                    SearchChatMessage(
                        role="MEM",
                        text="The other-Context answer request was cancelled.",
                    ),
                ),
                status="OTHER CONTEXTS CANCELLED",
                pending_answer=None,
            )
        if token != SEARCH_OUTSIDE_CONFIRMATION:
            return replace(
                state,
                messages=(
                    *state.messages,
                    SearchChatMessage(role="USER", text=text),
                    SearchChatMessage(
                        role="MEM",
                        text=(
                            "The wider scope was not confirmed. Type exactly "
                            f"`{SEARCH_OUTSIDE_CONFIRMATION}` to continue, or "
                            f"`{SEARCH_OUTSIDE_CANCELLATION}` to cancel."
                        ),
                    ),
                ),
                status="WAITING FOR OTHER CONTEXTS CONFIRMATION",
            )
        provider = connect_search_provider()
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
        state: SearchChatState,
        *,
        submitted_text: str,
        answer_question: str,
        interpreted_request: str,
        pending_clarification: str | None,
        include_outside: bool,
        provider: SearchAnswerProvider,
    ) -> SearchChatState:
        # The provider object has already passed the same runtime interface
        # check used by the dialogue adapters; keeping this method provider-
        # agnostic makes the two-turn confirmation path share one boundary.
        complete = getattr(provider, "complete", None)
        if not callable(complete):
            raise SearchError("Search answer provider is not available.")
        if not state.results or any(
            result.relevance != "primary" for result in state.results
        ):
            # Related fallbacks aid discovery but are not evidence that the
            # original query was satisfied. A REFINE turn must promote them
            # through a fresh primary ranking before answer synthesis.
            raise SearchError(
                "Related Search results cannot answer the original query. "
                "Refine the Search first."
            )
        visible_candidates = self._visible_candidates(state)
        visible = visible_result_evidence(visible_candidates)
        context = context_remainder_evidence(
            self.frame_candidates,
            visible_candidates,
        )
        outside = ()
        outside_status: SearchOutsideStatus = "NOT_REQUESTED"
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
            answer = synthesize_search_answer(
                answer_question,
                visible,
                context,
                outside,
                outside_status,
                provider,
                interpreted_request=interpreted_request,
                pending_clarification=pending_clarification,
            )
        except SearchAnswerCorpusTooLarge:
            if not include_outside:
                raise
            # A confirmed global scan can exceed the prototype corpus ceiling.
            # Preserve the same-Context answer and state that the outside scope
            # could not be completed instead of silently sampling a subset.
            outside = ()
            outside_status = "UNAVAILABLE"
            answer = synthesize_search_answer(
                answer_question,
                visible,
                context,
                outside,
                outside_status,
                provider,
                interpreted_request=interpreted_request,
                pending_clarification=pending_clarification,
            )
        rendered = render_search_answer_references(
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
                SearchChatMessage(role="USER", text=submitted_text),
                SearchChatMessage(role="MEM", text=rendered),
            ),
            status=_search_answer_status(outside_status),
            pending_answer=None,
        )


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _load_search_frame_roots(
    store: MemoryStore,
    root: Context,
    *,
    recursive: bool,
    resolve_embeds: bool,
) -> tuple[Context, ...]:
    """Compatibility adapter for the former Search-owned scope helper."""

    return load_readable_search_roots(
        store,
        (root.name,),
        include_descendants=recursive,
        follow_embeds=resolve_embeds,
        include_attached_reads=False,
    )


def _load_search_scope_roots(
    store: ReadableContextCatalog,
    target_names: Sequence[str],
    *,
    include_descendants: bool,
    follow_embeds: bool,
) -> tuple[Context, ...]:
    """Compatibility adapter for tests and retained Search callers."""

    return load_readable_search_roots(
        store,
        target_names,
        include_descendants=include_descendants,
        follow_embeds=follow_embeds,
    )


def _collect_search_frame_candidates(
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
    """Return the first canonical namespace segment below one Search root."""

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


def _chat_result(match: SearchMatch, index: int) -> SearchChatResult:
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
        raise SearchError("Search returned an unsupported result type.")
    return SearchChatResult(
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
        raise SearchError("Search cannot mix primary and related results.")
    if related_count:
        if len(related_queries) != 1 or None in related_queries:
            raise SearchError("Related Search results require one broader query.")
        return next(iter(related_queries)) or ""
    return ""


def _search_result_message(
    matches: Sequence[SearchMatch],
    *,
    refined: bool = False,
) -> str:
    related_query = _related_query_for_matches(matches)
    count = len(matches)
    noun = "Memory" if count == 1 else "Memories"
    suffix = " after refining the Search" if refined else ""
    if related_query:
        return (
            "I found no primary matches. "
            f"I am showing {count} related {noun}{suffix} for the broader "
            f"search: {related_query}."
        )
    return f"I found {count} matching {noun}{suffix}."


def _search_result_status(
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
) -> SearchChatState:
    related_query = _related_query_for_matches(matches)
    return SearchChatState(
        context_name=context_name,
        current_query=query,
        messages=(
            SearchChatMessage(role="USER", text=query),
            SearchChatMessage(
                role="MEM",
                text=_search_result_message(matches),
            ),
        ),
        results=tuple(
            _chat_result(match, index) for index, match in enumerate(matches, start=1)
        ),
        related_query=related_query,
        status=_search_result_status(matches),
    )


def _show_result_proposal(
    state: SearchChatState,
    action: SearchTurnAction,
    submitted_text: str,
) -> SearchShowProposal:
    matches = tuple(
        result for result in state.results if result.alias == action.selector
    )
    if len(matches) != 1:
        raise SearchError("The requested Search result is missing or ambiguous.")
    selected = matches[0]
    review = CommandReview(
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
    return SearchShowProposal(
        action=action,
        result=selected,
        review=review,
        submitted_text=submitted_text,
    )


def _apply_artifact_show_result(
    state: SearchChatState,
    proposal: SearchShowProposal,
) -> SearchChatState:
    """Inspect a frozen artifact without pretending it is an ordinary Memory."""
    action = proposal.action
    return replace(
        state,
        messages=(
            *state.messages,
            SearchChatMessage(role="USER", text=proposal.submitted_text),
            SearchChatMessage(
                role="MEM",
                text=(
                    f"{action.understanding}\n\n{action.question}\n\n"
                    f"{proposal.result.content}"
                ),
            ),
            SearchChatMessage(
                role="STATUS",
                text="ARTIFACT SHOWN",
            ),
        ),
        status=f"SHOWED {proposal.result.alias}",
    )


def _run_read_only_search_command(
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
        raise SearchError("Search refused a non-show follow-up command.")
    return subprocess.run(
        [sys.executable, "-m", "memcommit.adapters.console.entrypoint", *argv[1:]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def _apply_show_result(
    state: SearchChatState,
    proposal: SearchShowProposal,
) -> SearchChatState:
    try:
        completed = _run_read_only_search_command(proposal.review.argv)
    except subprocess.TimeoutExpired as error:
        raise SearchError("The mem show action timed out.") from error
    except OSError as error:
        raise SearchError("The mem show action could not be started.") from error
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise SearchError(
            "The mem show action failed" + (f": {detail}" if detail else ".")
        )
    actual_output = completed.stdout.strip()
    if not actual_output:
        raise SearchError("The mem show action returned no output.")
    action = proposal.action
    return replace(
        state,
        messages=(
            *state.messages,
            SearchChatMessage(
                role="USER",
                text=proposal.submitted_text,
            ),
            SearchChatMessage(
                role="MEM",
                text=f"{action.understanding}\n\n{action.question}",
            ),
            SearchChatMessage(
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


def _handle_search_turn(
    state: SearchChatState,
    text: str,
) -> SearchChatState:
    store = MemoryStore()
    access = resolve_context_access(
        store,
        state.context_name,
        current_name=store.current_context_name(),
        required_permission="READ",
    )
    read_store = freeze_readable_context_catalog(store, access)
    root = read_store.load(access.display_name)
    frame_roots = _load_search_frame_roots(
        read_store,
        root,
        recursive=True,
        resolve_embeds=True,
    )
    frame_candidates = _collect_search_frame_candidates(
        store,
        frame_roots,
        recursive=True,
        include_artifacts=not access.is_granted,
    )
    return SearchTurnController(
        # Other-Context confirmation retains its established profile-local
        # boundary; the unified catalog is only the selected Search frame.
        store=store,
        root_context=root,
        frame_roots=frame_roots,
        recursive=True,
        limit=5,
        frame_candidates=frame_candidates,
    )(state, text)


def _run_interactive_search(
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
) -> SearchChatSessionResult:
    controller = SearchTurnController(
        store=outside_store,
        root_context=root_context,
        frame_roots=frame_roots,
        recursive=recursive,
        limit=limit,
        frame_candidates=frame_candidates,
    )
    result = run_search_chat_session(
        _initial_chat_state(root_context.name, query, matches),
        handle_turn=controller,
    )
    typer.echo(
        f"Search dialogue closed with {len(result.state.results)} visible "
        f"result(s) after {len(result.submitted_turns)} follow-up turn(s)."
    )
    return result


def _run_search_request(
    store: MemoryStore,
    catalog: ReadableContextCatalog,
    request: SearchRequest,
    *,
    observer=None,
) -> SearchResponse:
    """Compatibility adapter over the terminal-independent Search runtime."""

    return execute_search(
        request,
        store=store,
        catalog=catalog,
        provider_factory=connect_search_provider,
        observer=observer,
    )


def _render_search_response(
    response: SearchResponse,
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
    if not response.results:
        typer.secho(heading, bold=True)
        typer.echo("  (no matching items)")
        return
    if response.related_query:
        if len(target_names) == 1:
            typer.secho(heading, bold=True)
            typer.echo("  (no primary matches)")
            typer.echo()
        typer.secho("RELATED RESULTS", bold=True)
        typer.echo(
            "  No matching results for: " + display_escape_text(response.request.query)
        )
        typer.echo("  Broader search: " + display_escape_text(response.related_query))
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


def _open_search_workbench(
    store: MemoryStore,
    access: ContextAccess,
    *,
    current_name: str | None,
    initial_targets: Sequence[str] = (),
    include_descendants: bool,
    follow_embeds: bool,
    limit: int,
) -> None:
    """Open a blank, query-focused Search over one frozen readable catalog."""

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
    workbench_result = run_search_workbench(
        names,
        current=displayed_current,
        initial_target=initial_target,
        initial_targets=initial_targets or (initial_target,),
        initial_include_descendants=include_descendants,
        initial_follow_embeds=follow_embeds,
        limit=limit,
        run_search=lambda request: _run_search_request(
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
    materialized = execute_search_materialization(
        SearchMaterializationRequest(
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
            raise ValueError("Search Context roots must be distinct.")
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
        # Semantic retrieval is derived use even for one selected Context;
        # multiple ownership domains additionally require COMBINE. Keep this
        # before provider construction so READ-only Grants remain browse-only.
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
            _open_search_workbench(store, access, **workbench_options)
        except (
            SearchMaterializationError,
            SearchError,
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

    request = SearchRequest(
        query=query,
        target_names=target_names,
        include_descendants=include_descendants,
        follow_embeds=follow_embeds,
        limit=limit,
    )
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
            response = _run_search_request(store, catalog, request)
        else:
            catalog = freeze_readable_context_catalog(
                store,
                access,
                include_query_routes=follow_embeds,
            )
            with CommandProgress(
                "SEARCH",
                "connecting provider",
                total=3,
            ) as progress:

                def observe(stage: SearchStage) -> None:
                    if stage == "SEARCHING":
                        progress.update("ranking candidates", step=2)
                    elif stage == "CHECKING_COVERAGE":
                        progress.update("checking namespace coverage", step=3)

                response = _run_search_request(
                    store,
                    catalog,
                    request,
                    observer=observe,
                )
        _render_search_response(
            response,
            target_names=target_names,
            all_readable_contexts=all_contexts,
        )
    except (
        SearchError,
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

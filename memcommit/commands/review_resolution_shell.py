"""Run durable semantic reviews through the common Resolution workbench."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.commands.resolution_workbench_shell import (
    run_resolution_workbench_shell,
)
from memcommit.context import Context, Memory
from memcommit.resolution_workbench import (
    ResolutionContextLocation,
    ResolutionIssueEvidence,
    ResolutionIssuePresentation,
    ResolutionIssueSource,
    ResolutionItem,
    ResolutionNavigation,
    ResolutionOption,
    ResolutionWorkbenchView,
)
from memcommit.operations.review.model import (
    REVIEW_RESPONSE_CHAR_LIMIT,
    ReviewError,
    ReviewSession,
)
from memcommit.reviewing.session_navigation import SessionWorkbenchNavigation


def _direct_memories(ctx: Context) -> tuple[Memory, ...]:
    return tuple(item for item in ctx.iter_items() if isinstance(item, Memory))


def review_resolution_view(
    session: ReviewSession, ctx: Context
) -> ResolutionWorkbenchView:
    """Project a durable ReviewSession without changing its storage schema."""

    memories = _direct_memories(ctx)
    memory_by_uid = {memory.uid: memory for memory in memories}
    ordinal_by_uid = {
        memory.uid: ordinal for ordinal, memory in enumerate(memories, start=1)
    }
    items: list[ResolutionItem] = []
    for finding in session.ordered_items():
        response = session.responses.get(finding.uid)
        sources = tuple(
            ResolutionIssueSource(
                label=f"SOURCE {index}",
                context_name=session.context_name,
                memory_uid=memory_uid,
                content=(
                    memory_by_uid[memory_uid].content
                    if memory_uid in memory_by_uid
                    else "[source Memory unavailable]"
                ),
                ordinal=ordinal_by_uid.get(memory_uid),
            )
            for index, memory_uid in enumerate(finding.source_uids, start=1)
        )
        title = " ↔ ".join(" ".join(source.content.split())[:120] for source in sources)
        items.append(
            ResolutionItem(
                uid=finding.uid,
                kind=(
                    "ATOMIZE UNCERTAINTY" if session.kind == "atomize" else "AMBIGUITY"
                ),
                status=(
                    "ANSWERED" if response is not None and response.answered else "OPEN"
                ),
                priority=finding.clarification,
                title=title or finding.uid,
                summary=finding.reason,
                obligation=(
                    "REQUIRED"
                    if finding.clarification in {"REQUIRED", "RECONCILE"}
                    else "OPTIONAL"
                ),
                response_state=(
                    "ANSWERED" if response is not None and response.answered else "OPEN"
                ),
                response_text=response.text if response is not None else "",
                question=finding.question,
                options=tuple(
                    ResolutionOption(choice.uid, choice.label, choice.text)
                    for choice in finding.choices
                ),
                selected_option_uid=(
                    response.selected_choice_uid if response is not None else None
                ),
                issue_presentation=ResolutionIssuePresentation(
                    evidence=(
                        ResolutionIssueEvidence(
                            group_heading="",
                            sources_heading=(
                                "SOURCE MEMORY"
                                if len(sources) == 1
                                else "SOURCE MEMORIES"
                            ),
                            classification=(
                                f"{finding.interpretation} · {finding.clarification}"
                            ),
                            reason_heading=(
                                "WHY ATOMIZE IS BLOCKED"
                                if session.kind == "atomize"
                                else "WHY THIS IS UNCLEAR"
                            ),
                            reason=finding.reason,
                            sources=sources,
                        ),
                    ),
                    prompt_heading="CLARIFICATION QUESTION",
                    options_heading="PROPOSED READINGS",
                    other_option_label="Different reading",
                    response_heading="RESPONSE",
                ),
            )
        )
    return ResolutionWorkbenchView(
        operation=f"REVIEW {session.kind.upper()}",
        artifact_uid=session.uid,
        revision=session.context_digest,
        title=f"Review {session.kind}",
        route=session.context_name,
        status="OPEN",
        metrics=(),
        overview=(
            "Review source-linked findings and save responses without changing "
            "any Context or Memory."
        ),
        list_label="ACTIONABLE FINDINGS",
        items=tuple(items),
        empty_message="No review findings.",
        results_label="EXACT RESULTS",
        results=(),
        capabilities=frozenset({"SUBMIT_ITEM"}),
        context_locations=(ResolutionContextLocation("SOURCE", session.context_name),),
        show_results=False,
    )


def run_review_resolution_shell(
    session: ReviewSession,
    ctx: Context,
    *,
    save: Callable[[ReviewSession], None],
    read_only: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ReviewSession:
    """Open a ReviewSession through the service-wide response surface."""

    navigation = ResolutionNavigation(selected_item_uid=session.cursor_uid)
    workbench_navigation = SessionWorkbenchNavigation()

    def load_draft(item_uid: str) -> tuple[str | None, str]:
        response = session.responses.get(item_uid)
        if response is None:
            return None, ""
        return response.selected_choice_uid, response.text

    def validate_response(text: str) -> None:
        if len(text) > REVIEW_RESPONSE_CHAR_LIMIT:
            raise ReviewError(
                "Response is too long to save "
                f"({len(text):,}/{REVIEW_RESPONSE_CHAR_LIMIT:,} characters)."
            )

    def save_draft(item_uid: str, choice_uid: str | None, text: str) -> None:
        validate_response(text)
        item = next(item for item in session.items if item.uid == item_uid)
        if choice_uid is not None and choice_uid not in {
            choice.uid for choice in item.choices
        }:
            raise ReviewError("Unknown review choice.")
        response = session.response_for(item_uid)
        response.selected_choice_uid = choice_uid
        response.text = text
        session.cursor_uid = item_uid
        save(session)

    def toggle_sort() -> None:
        session.toggle_sort()
        save(session)

    run_resolution_workbench_shell(
        lambda: review_resolution_view(session, ctx),
        navigation=navigation,
        workbench_navigation=workbench_navigation,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
        terminal_label="Review",
        snapshot_hint="Use 'mem review --snapshot' to inspect the saved session.",
        draft_loader=load_draft,
        draft_saver=None if read_only else save_draft,
        response_validator=validate_response,
        save_draft_on_close=not read_only,
        toggle_sort=None if read_only else toggle_sort,
        split_viewer_items=True,
        read_only=read_only,
    )
    if not read_only and navigation.selected_item_uid is not None:
        session.cursor_uid = navigation.selected_item_uid
    if not read_only:
        save(session)
    return session

"""Start, retain, and create a new Context-rooted Ground."""

from __future__ import annotations

from collections.abc import Sequence
import subprocess
from typing import Literal

import typer

from memcommit.adapters.console.commands.ground_workbench.ground.shell import (
    GroundShellMemoryDraft,
    GroundShellProposal,
    GroundShellRuleDraft,
    proposal_argv,
    run_ground_shell,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.commands.ground_workbench.ground.workspace.location import (
    GroundWorkspaceLocationSetup,
    choose_ground_workspace_location,
)
from memcommit.adapters.console.commands.ground_workbench.ground.workspace.viewer.screen import (
    run_ground_workspace_viewer,
)
from memcommit.application.operations.ground_workbench.ground.context_catalog import (
    discover_ground_context_locators,
    select_ground_context_locators,
)
from memcommit.application.operations.ground_workbench.ground.dialogue import (
    GROUND_DIALOGUE_NAME_LIMIT,
    GROUND_DIALOGUE_USER_TEXT_LIMIT,
    GroundDialogueError,
    GroundDialogueProposal,
    interpret_ground_dialogue,
)
from memcommit.application.operations.ground_workbench.ground.contracts import GroundError
from memcommit.application.operations.ground_workbench.ground.workspace_draft import (
    GroundWorkspaceDraft,
    GroundWorkspaceDraftError,
    GroundWorkspaceMemoryDraft,
    GroundWorkspaceRuleDraft,
    ground_workspace_draft_digest,
)
from memcommit.application.operations.ground_workbench.ground.workspace_draft_store import (
    GroundWorkspaceDraftStore,
)
from memcommit.application.operations.ground_workbench.ground.workspace_model import (
    GroundWorkspaceError,
    ground_workspace_context_names,
)
from memcommit.application.operations.ground_workbench.ground.workspace_runtime import (
    ground_workspace_exists,
    load_ground_workspace,
    load_ground_workspace_navigation_contexts,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import connect_codex_chatgpt_provider

from . import apply as approved_apply


def _validated_start_request(value: str) -> str:
    """Validate one unsaved natural-language Ground entry."""
    text = value.strip()
    if not text or len(text) > GROUND_DIALOGUE_USER_TEXT_LIMIT:
        raise GroundDialogueError(
            "Ground chat input must be non-empty and no longer than "
            f"{GROUND_DIALOGUE_USER_TEXT_LIMIT} characters."
        )
    return text


def _current_context_name_for_ground(store: MemoryStore) -> str | None:
    """Snapshot the local current pointer without opening its Context record."""
    try:
        value = store.current_context_name()
    except (OSError, TypeError, ValueError):
        return None
    return value if isinstance(value, str) and value else None


def _validate_ground_workspace_save_location(
    store: MemoryStore,
    name: str,
    *,
    exclude_draft_uid: str | None = None,
) -> str:
    """Validate one exact require-new root without creating Store records."""

    canonical = validate_portable_context_name(name)
    if len(canonical) > GROUND_DIALOGUE_NAME_LIMIT:
        raise ValueError("Ground Save Location is too long for one dialogue turn.")
    for context_name in ground_workspace_context_names(canonical):
        store.assert_context_creatable(context_name)
    existing_draft = GroundWorkspaceDraftStore(store).find_by_workspace_name(canonical)
    if existing_draft is not None and existing_draft.uid != exclude_draft_uid:
        raise FileExistsError(
            f"A resumable Ground draft already uses '{canonical}'. Open it "
            "from the Ground launcher."
        )
    return canonical


def _suggest_ground_workspace_save_location(
    store: MemoryStore,
    *,
    current_context_name: str | None,
) -> str:
    """Suggest one collision-free root beneath Current when available."""

    stem = (
        f"{current_context_name}/ground"
        if current_context_name is not None
        else "ground"
    )
    candidate = stem
    suffix = 2
    while True:
        try:
            return _validate_ground_workspace_save_location(store, candidate)
        except FileExistsError:
            candidate = f"{stem}-{suffix}"
            suffix += 1


def _choose_ground_workspace_save_location(
    store: MemoryStore,
    *,
    initial_name: str | None = None,
    exclude_draft_uid: str | None = None,
) -> str | None:
    """Collect one exact new root through the shared Context-name control."""

    context_names = tuple(store.list_context_names())
    current_context_name = _current_context_name_for_ground(store)
    suggested_name = (
        _suggest_ground_workspace_save_location(
            store,
            current_context_name=current_context_name,
        )
        if initial_name is None
        else initial_name
    )
    return choose_ground_workspace_location(
        GroundWorkspaceLocationSetup(
            initial_name=suggested_name,
            current_context=current_context_name,
            context_names=context_names,
            validate_name=lambda name: (
                _validate_ground_workspace_save_location(
                    store,
                    name,
                    exclude_draft_uid=exclude_draft_uid,
                )
            ),
        )
    )


def _interpret_new_ground_turn(
    text: str,
    *,
    context_names: Sequence[str] | None = None,
    ground_name: str | None = None,
):
    if ground_name is not None:
        context_names = ()
    if context_names is None:
        locators = discover_ground_context_locators(MemoryStore(create=False))
        context_names = tuple(
            locator.name for locator in select_ground_context_locators(text, locators)
        )
    turn = interpret_ground_dialogue(
        text,
        connect_codex_chatgpt_provider,
        context_names=context_names,
        ground_name=ground_name,
    )
    store = MemoryStore(create=False)
    for suggestion in turn.new_context_suggestions:
        try:
            # This is a read-only early check. A future approved `mem init`
            # must repeat it at its own locked save boundary because the
            # display-only suggestion conveys no creation authority.
            store.assert_context_creatable(suggestion.context_name)
        except (FileExistsError, OSError, ValueError) as error:
            raise GroundDialogueError(
                "The suggested new Context name is not currently creatable."
            ) from error
    if isinstance(turn, GroundDialogueProposal):
        if ground_workspace_exists(store, turn.ground_name):
            raise GroundDialogueError(
                f"Ground '{turn.ground_name}' already exists. Refine the "
                "Save Location or resume that Ground explicitly."
            )
    return turn


def _apply_new_ground_proposal(
    proposal: GroundShellProposal,
) -> str:
    """Run the exact creation argv frozen by the approval screen."""
    store = MemoryStore(create=False)
    if ground_workspace_exists(store, proposal.ground_name):
        raise GroundError(
            f"Ground '{proposal.ground_name}' was created before approval; "
            "nothing was overwritten."
        )
    argv = proposal_argv(proposal)
    try:
        result = approved_apply._run_approved_ground_command(argv)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GroundError(
            "The approved Ground command could not be completed; nothing "
            "was confirmed as applied."
        ) from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GroundError(
            "The approved Ground command failed"
            + (f": {safe_terminal_text(detail)}" if detail else ".")
        )
    return result.stdout.strip()


def _proposal_from_workspace_draft(
    draft: GroundWorkspaceDraft,
) -> GroundShellProposal:
    return GroundShellProposal(
        ground_name=draft.workspace_name,
        goal=draft.goal,
        understanding=draft.understanding,
        question=draft.question,
        rule_drafts=tuple(
            GroundShellRuleDraft(
                content=item.content,
                rationale=item.rationale,
                origin=item.origin,
                source_spans=item.source_spans,
            )
            for item in draft.rule_drafts
        ),
        memory_drafts=tuple(
            GroundShellMemoryDraft(
                content=item.content,
                expected=item.expected,
                rationale=item.rationale,
                case_role=item.case_role,
                disposition=item.disposition,
                rule_draft_index=item.rule_draft_index,
                origin=item.origin,
                source_spans=item.source_spans,
            )
            for item in draft.memory_drafts
        ),
    )


def _workspace_draft_from_proposal(
    proposal: GroundShellProposal,
    *,
    submitted_turns: tuple[str, ...],
    current: GroundWorkspaceDraft | None,
) -> GroundWorkspaceDraft:
    if proposal.context_suggestions or proposal.new_context_suggestions:
        raise GroundWorkspaceDraftError(
            "A fixed-location Ground draft cannot retain Context suggestions."
        )
    rules = tuple(
        GroundWorkspaceRuleDraft(
            content=item.content,
            rationale=item.rationale,
            origin=item.origin,
            source_spans=item.source_spans,
        )
        for item in proposal.rule_drafts
    )
    memories = tuple(
        GroundWorkspaceMemoryDraft(
            content=item.content,
            expected=item.expected,
            rationale=item.rationale,
            case_role=item.case_role,
            disposition=item.disposition,
            rule_draft_index=item.rule_draft_index,
            origin=item.origin,
            source_spans=item.source_spans,
        )
        for item in proposal.memory_drafts
    )
    if current is None:
        return GroundWorkspaceDraft.create(
            workspace_name=proposal.ground_name,
            goal=proposal.goal,
            understanding=proposal.understanding,
            question=proposal.question,
            submitted_turns=submitted_turns,
            rule_drafts=rules,
            memory_drafts=memories,
        )
    unchanged = (
        current.workspace_name == proposal.ground_name
        and current.goal == proposal.goal
        and current.understanding == proposal.understanding
        and current.question == proposal.question
        and current.submitted_turns == submitted_turns
        and current.rule_drafts == rules
        and current.memory_drafts == memories
    )
    if unchanged:
        return current
    return current.revise(
        workspace_name=proposal.ground_name,
        goal=proposal.goal,
        understanding=proposal.understanding,
        question=proposal.question,
        submitted_turns=submitted_turns,
        rule_drafts=rules,
        memory_drafts=memories,
    )


def _retain_ground_workspace_draft(
    store: MemoryStore,
    *,
    proposal: GroundShellProposal,
    submitted_turns: tuple[str, ...],
    current: GroundWorkspaceDraft | None,
) -> GroundWorkspaceDraft:
    draft = _workspace_draft_from_proposal(
        proposal,
        submitted_turns=submitted_turns,
        current=current,
    )
    if current is not None and draft == current:
        return current
    GroundWorkspaceDraftStore(store).save(
        draft,
        expected_digest=(
            ground_workspace_draft_digest(current) if current is not None else None
        ),
    )
    return draft


def _run_new_ground_shell(
    initial_request: str = "",
    *,
    ground_name: str | None = None,
    draft: GroundWorkspaceDraft | None = None,
) -> Literal["CLOSED", "BACK_TO_PICKER"]:
    store = MemoryStore(create=False)
    if draft is not None:
        if ground_name is not None and ground_name != draft.workspace_name:
            raise GroundWorkspaceDraftError(
                "The Ground draft does not match its Save Location."
            )
        ground_name = draft.workspace_name
    # New physical Grounds no longer begin by ranking existing Contexts. The
    # session starts blank and owns a separate Save Location control above its
    # Goal; external material enters /contexts through later explicit actions.
    locators = ()
    semantic_ground_name = {"value": ground_name}
    # Current is only an at-launch orientation snapshot. It remains local to
    # the shell: the provider sees the same bounded name catalog as before,
    # without a mutable "this one is current" marker or any Context content.
    current_context_name = _current_context_name_for_ground(store)

    def interpret(text: str):
        context_names = tuple(
            locator.name for locator in select_ground_context_locators(text, locators)
        )
        kwargs = {"context_names": context_names}
        if semantic_ground_name["value"] is not None:
            kwargs["ground_name"] = semantic_ground_name["value"]
        turn = _interpret_new_ground_turn(text, **kwargs)
        if semantic_ground_name["value"] is None and isinstance(
            turn, GroundDialogueProposal
        ):
            # A provider-proposed initial name becomes the visible local plan
            # for later turns, but creates nothing and remains replaceable by
            # the person through LOCATION.
            semantic_ground_name["value"] = turn.ground_name
        return turn

    def validate_new_context(name: str) -> str:
        # This is only a read-only early check for the local editor. The
        # separately approved `mem init` must repeat it under its own lock.
        store.assert_context_creatable(name)
        return name

    def choose_save_location(current: str | None) -> str | None:
        selected = _choose_ground_workspace_save_location(
            store,
            initial_name=current,
            exclude_draft_uid=(draft.uid if draft is not None else None),
        )
        if selected is not None:
            # The shell and semantic adapter share one process-local Location
            # plan so a slash-delimited Context root is validated as the exact
            # user-owned target, never as a legacy portable Ground name.
            semantic_ground_name["value"] = selected
        return selected

    shell_kwargs = {
        "interpret": interpret,
        "apply": _apply_new_ground_proposal,
        "current_context_name": current_context_name,
        "validate_new_context": validate_new_context,
        "choose_save_location": choose_save_location,
    }
    if ground_name is not None:
        shell_kwargs["ground_name"] = ground_name
    if draft is not None:
        shell_kwargs["initial_proposal"] = _proposal_from_workspace_draft(draft)
        shell_kwargs["initial_submitted_turns"] = draft.submitted_turns
    if initial_request:
        shell_kwargs["initial_request"] = initial_request
    result = run_ground_shell(**shell_kwargs)
    if result.status == "APPLIED":
        proposal = result.proposal
        if proposal is None:
            raise GroundError("The approved Ground was not available for continuation.")
        workspace_store = MemoryStore(create=False)
        try:
            workspace = load_ground_workspace(
                workspace_store,
                proposal.ground_name,
            )
        except (FileNotFoundError, GroundWorkspaceError, OSError, ValueError):
            raise GroundError("The approved Ground could not be reloaded.")
        if draft is not None:
            try:
                GroundWorkspaceDraftStore(store).delete(
                    draft.uid,
                    expected_digest=ground_workspace_draft_digest(draft),
                )
            except (OSError, RuntimeError, ValueError):
                # The physical workspace is authoritative after creation.
                # Catalog discovery suppresses a stale draft with the same
                # root, so cleanup failure cannot fabricate a second Ground.
                typer.secho(
                    "Ground created; its stale draft receipt could not be "
                    "removed and will remain hidden.",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
        run_ground_workspace_viewer(
            workspace,
            navigation_contexts=load_ground_workspace_navigation_contexts(
                workspace_store,
                workspace,
            ),
        )
        return "CLOSED"
    if result.proposal is not None:
        _retain_ground_workspace_draft(
            store,
            proposal=result.proposal,
            submitted_turns=result.submitted_turns,
            current=draft,
        )
    if result.status == "BACK_TO_PICKER":
        return "BACK_TO_PICKER"
    if result.proposal is not None:
        typer.echo("Ground chat closed. Draft saved; nothing was created.")
    else:
        typer.echo("Ground chat cancelled. Nothing was created.")
    return "CLOSED"

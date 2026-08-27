"""Project local Branch placement into shared compact Endpoint Setup."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.exact_command_review import ExactCommandReview
from memcommit.adapters.interfaces.tui.components.endpoint_setup import (
    EndpointSetupDraft,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
)
from memcommit.adapters.interfaces.tui.operations.branch.model import (
    BranchEndpointSelection,
)


def branch_endpoint_setup_spec(
    local_names: Sequence[str],
    *,
    current: str | None,
    suggest_name: Callable[[str], str],
    validate_name: Callable[[str], object],
) -> EndpointSetupSpec:
    """Build Branch's one-shape Source, range, and parent-assisted target."""

    names = tuple(local_names)
    if (
        not names
        or len(set(names)) != len(names)
        or any(not isinstance(name, str) or not name for name in names)
    ):
        raise ValueError("Interactive Branch requires ordinary local Contexts.")
    if not callable(suggest_name) or not callable(validate_name):
        raise TypeError("Interactive Branch requires name callbacks.")
    initial_source = current if current in names else names[0]
    initial_target = suggest_name(initial_source)

    def suggest_from_endpoints(values: Mapping[str, str]) -> str:
        source_name = values.get("A", "").strip()
        if not source_name:
            raise ValueError("FROM needs a Context name before suggesting TO.")
        return suggest_name(source_name)

    return EndpointSetupSpec(
        title="MEM BRANCH",
        subtitle="CHOOSE SOURCE AND NEW CONTEXT",
        modes=(
            EndpointSetupMode(
                "BRANCH",
                "FROM A → TO B",
                (
                    "A chooses one local Context or lexical subtree; B is one "
                    "exact new root whose descendant suffixes are preserved."
                ),
                active_role_uids=("A", "B"),
                role_labels=(("A", "FROM"), ("B", "TO")),
                descendant_role_uids=frozenset({"A"}),
                memory_focus_role_uids=frozenset(),
            ),
        ),
        initial_mode_uid="BRANCH",
        screen_layout="COMPACT_FORM",
        roles=(
            EndpointSetupRole(
                "A",
                "A · FROM CONTEXT",
                names,
                frozenset(names),
                initial_source,
                current_context=current,
                allow_descendants=True,
            ),
            EndpointSetupRole(
                "B",
                "B · TO · NEW CONTEXT",
                names,
                frozenset(),
                initial_source,
                current_context=current,
                allow_new=True,
                new_label="EXACT NEW CONTEXT NAME",
                initial_new_name=initial_target,
                prefer_new=True,
                new_name_validator=validate_name,
                new_name_suggester=suggest_from_endpoints,
                new_parent_locator=True,
            ),
        ),
        action_label="CREATE BRANCH AND SWITCH",
        command_verb="APPLY",
    )


def branch_exact_command_review(draft: EndpointSetupDraft) -> ExactCommandReview:
    """Render the exact public Branch command represented by one typed draft."""

    source = draft.value("A")
    target = draft.value("B")
    if not target.create:
        raise ValueError("TO must be one exact new Context name.")
    argv = [
        "mem",
        "branch",
        target.context_name,
        "--from",
        source.context_name,
        (
            "--source-descendants"
            if source.include_descendants
            else "--source-root-only"
        ),
    ]
    scope = (
        "the frozen local Source root and lexical descendants"
        if source.include_descendants
        else "the frozen local Source root only"
    )
    return ExactCommandReview(
        tuple(argv),
        (
            f"Create the exact new Branch target from {scope}.",
            "Switch the current Context to the new target root after publication.",
        ),
    )


def choose_branch_endpoint_setup(
    local_names: Sequence[str],
    *,
    current: str | None,
    suggest_name: Callable[[str], str],
    validate_name: Callable[[str], object],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> BranchEndpointSelection | None:
    """Return one compact Branch draft without creating or switching Contexts."""

    draft = run_endpoint_setup(
        branch_endpoint_setup_spec(
            local_names,
            current=current,
            suggest_name=suggest_name,
            validate_name=validate_name,
        ),
        validate_draft=lambda value: _validate_branch_draft(
            value,
            existing_names=frozenset(local_names),
        ),
        command_review=branch_exact_command_review,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    source = draft.value("A")
    target = draft.value("B")
    return BranchEndpointSelection(
        source_name=source.context_name,
        target_name=target.context_name,
        include_descendants=source.include_descendants,
    )


def _validate_branch_draft(
    draft: EndpointSetupDraft,
    *,
    existing_names: frozenset[str],
) -> str | None:
    target = draft.value("B")
    if not target.create or target.context_name in existing_names:
        return "TO must be a new Context."
    return None


__all__ = [
    "branch_endpoint_setup_spec",
    "branch_exact_command_review",
    "choose_branch_endpoint_setup",
]

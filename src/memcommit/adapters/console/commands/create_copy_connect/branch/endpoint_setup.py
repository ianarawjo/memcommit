"""Project local Branch placement into shared compact Endpoint Setup."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.create_copy_connect.branch import command_codec as branch_command_codec
from memcommit.adapters.console.commands.create_copy_connect.branch.receipt import (
    BranchCreationReceipt,
)
from memcommit.adapters.console.terminal.components.endpoint_setup import (
    EndpointCommandBinding,
    EndpointSetupDraft,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
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


branch_exact_command_review = branch_command_codec.build_review


def choose_branch_creation(
    local_names: Sequence[str],
    *,
    current: str | None,
    suggest_name: Callable[[str], str],
    validate_name: Callable[[str], object],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> BranchCreationReceipt | None:
    """Return one compact Branch draft without creating or switching Contexts."""

    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive Branch setup requires a terminal.")
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
        command_editor=EndpointCommandBinding(
            form=branch_command_codec.BRANCH_COMMAND_FORM,
            review=branch_exact_command_review,
            parse=branch_command_codec.parse_endpoint_argv,
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=False,
    )
    if draft is None:
        return None
    source = draft.value("A")
    target = draft.value("B")
    return _validated_branch_creation_receipt(
        source_name=source.context_name,
        target_name=target.context_name,
        include_descendants=source.include_descendants,
    )


def _validated_branch_creation_receipt(
    *,
    source_name: str,
    target_name: str,
    include_descendants: bool,
) -> BranchCreationReceipt:
    """Preserve the former endpoint-selection validation before translation."""

    if (
        not isinstance(source_name, str)
        or not source_name
        or not isinstance(target_name, str)
        or not target_name
        or type(include_descendants) is not bool
        or any(character in source_name + target_name for character in "\r\n")
    ):
        raise ValueError("Branch setup requires exact one-line Context names.")
    return BranchCreationReceipt(
        source_name=source_name,
        target_name=target_name,
        include_descendants=include_descendants,
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
    "choose_branch_creation",
]

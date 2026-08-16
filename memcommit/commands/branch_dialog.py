"""Branch-specific adapter for the common endpoint and placement shell."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.commands.session_endpoint_setup import (
    EndpointModeSpec,
    EndpointRoleSpec,
    EndpointSetupDraft,
    choose_session_endpoints,
)
from memcommit.commands.context_picker import ContextMemoryRow


@dataclass(frozen=True)
class BranchCreationReceipt:
    """One frozen Source range and exact require-new branch target."""

    source_name: str
    target_name: str
    include_descendants: bool = False

    @property
    def new_name(self) -> str:
        """Compatibility spelling for callers that only accepted new targets."""

        return self.target_name


def choose_branch_creation(
    local_names: Sequence[str],
    *,
    current: str | None,
    suggest_name: Callable[[str], str],
    validate_name: Callable[[str], None],
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> BranchCreationReceipt | None:
    """Choose FROM plus a parent-assisted exact require-new TO."""

    names = tuple(local_names)
    if (
        not names
        or len(set(names)) != len(names)
        or any(not isinstance(name, str) or not name for name in names)
    ):
        raise ValueError("Interactive Branch requires ordinary local Contexts.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive Branch setup requires a terminal.")
    initial_source = current if current in names else names[0]

    def validate_draft(draft: EndpointSetupDraft) -> str | None:
        target = draft.value("B")
        return None if target.create else "Branch TO must be a new Context."

    draft = choose_session_endpoints(
        names,
        title="MEM BRANCH",
        modes=(
            EndpointModeSpec(
                "BRANCH",
                "FROM A → TO B",
                ("A", "B"),
                {
                    "A": "A · FROM CONTEXT",
                    "B": "B · TO · NEW CONTEXT",
                },
                (
                    "A chooses this Context or its lexical subtree; B creates "
                    "one exact new root and preserves descendant suffixes."
                ),
                descendant_roles=frozenset({"A"}),
            ),
        ),
        roles=(
            EndpointRoleSpec(
                "A",
                frozenset(names),
                initial_source,
                allow_descendants=True,
            ),
            EndpointRoleSpec(
                "B",
                frozenset(names),
                initial_source,
                allow_new=True,
                new_label="EXACT NEW CONTEXT NAME",
                initial_new_name=suggest_name(initial_source),
                prefer_new=True,
                new_name_suggester=lambda selected: suggest_name(selected["A"]),
                new_parent_locator=True,
            ),
        ),
        initial_mode_uid="BRANCH",
        memory_loader=memory_loader,
        validate_draft=validate_draft,
        app_input=app_input,
        app_output=app_output,
        require_tty=False,
    )
    if draft is None:
        return None
    source = draft.value("A")
    target = draft.value("B")
    # The common shell validates exact syntax and frozen-catalog collisions;
    # the operation-owned validator additionally protects storage-path policy.
    validate_name(target.context_name)
    return BranchCreationReceipt(
        source_name=source.context_name,
        target_name=target.context_name,
        include_descendants=source.include_descendants,
    )

"""Detailed Help topics owned by Profile."""

from memcommit.help_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


PROFILE_DETAILS = (
    OperationComparisonDetail(
        id="management-actions",
        operation="profile",
        title="PROFILE MANAGEMENT",
        use_when="Choosing a Profile creation, selection, rename, or removal action.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "The interactive picker and explicit Profile subcommands share the "
            "same managed Profile registry. Removal is permanent and is named "
            "remove, not delete, in the CLI."
        ),
        options=(
            OperationComparisonOption(
                label="CREATE",
                guidance=(
                    "Press N in the picker, or use mem profile create. The empty "
                    "Profile is not selected automatically."
                ),
            ),
            OperationComparisonOption(
                label="SELECT",
                guidance="Press Enter in the picker, or use mem profile use.",
            ),
            OperationComparisonOption(
                label="RENAME",
                guidance=(
                    "Press R on a Profile row, or use mem profile rename. "
                    "Top-level mem rename is reserved for Context namespaces."
                ),
            ),
            OperationComparisonOption(
                label="RENAME STUDY",
                guidance=(
                    "Press R on a Study heading, or use mem profile rename-study."
                ),
            ),
            OperationComparisonOption(
                label="REMOVE",
                guidance=(
                    "Press D in the picker, or use mem profile remove. Switch "
                    "away before removing the current Profile."
                ),
            ),
            OperationComparisonOption(
                label="REMOVE STUDY",
                guidance=(
                    "Press D on a Study heading, or use mem profile remove-study."
                ),
            ),
        ),
    ),
)


__all__ = ["PROFILE_DETAILS"]

"""Detailed Help topics owned by Revert."""

from memcommit.help_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


REVERT_DETAILS = (
    OperationComparisonDetail(
        id="selection-routes",
        operation="revert",
        title="REVERT ROUTES",
        use_when="Choosing how to identify and restore one checkpoint unit.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Every route restores one globally identified checkpoint unit. A "
            "recursive manual Checkpoint restores all of its recorded local "
            "members atomically; natural-language selection uses semantic lookup."
        ),
        options=(
            OperationComparisonOption(
                label="EXACT CHECKPOINT",
                guidance=(
                    "Resolve an exact checkpoint UID or unique prefix across the "
                    "local Profile and restore its complete recovery unit."
                ),
            ),
            OperationComparisonOption(
                label="INTERACTIVE",
                guidance=(
                    "Open the current Context's history, inspect one revision's "
                    "complete result, and approve it."
                ),
            ),
            OperationComparisonOption(
                label="NATURAL-LANGUAGE",
                guidance=(
                    "Use semantic history lookup, then review the selected "
                    "checkpoint before restoration."
                ),
            ),
            OperationComparisonOption(
                label="--DISCARD-NEWER",
                guidance=(
                    "Explicitly remove newer active checkpoint files; the "
                    "default keeps all checkpoints."
                ),
            ),
        ),
    ),
)


__all__ = ["REVERT_DETAILS"]

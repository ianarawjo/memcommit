"""Detailed Help topics owned by Add."""

from memcommit.help_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


ADD_DETAILS = (
    OperationComparisonDetail(
        id="copy-or-link",
        operation="add",
        title="COPY OR LINK",
        use_when=(
            "Choosing whether supplied material should become new Memory content "
            "or point to an existing Memory or Context."
        ),
        discovery=DetailDiscovery.TOOL_SELECTION,
        discovery_summary=(
            "Add stores input literally; use Reference for an immutable Memory "
            "snapshot and Embed for a live Memory or Context link."
        ),
        explanation=(
            "Text passed to Add is always stored literally as Memory content. "
            "Entering a Memory UID or Context name does not copy that object; "
            "it creates a new Memory containing that text."
        ),
        options=(
            OperationComparisonOption(
                label="INDEPENDENT WORK",
                guidance=(
                    "Branch the containing Context and merge it later, or copy "
                    "the Memory content and add it directly."
                ),
            ),
            OperationComparisonOption(
                label="EXACT MEMORY VERSION",
                guidance=(
                    "Use mem reference to retain an immutable snapshot of the "
                    "reviewed Source Memory. Run it bare interactively, or use "
                    "mem reference MEMORY_SELECTOR --from SOURCE_CONTEXT."
                ),
            ),
            OperationComparisonOption(
                label="LIVE MEMORY",
                guidance=(
                    "Use mem embed MEMORY --from SOURCE to follow the Source "
                    "Memory's current content."
                ),
            ),
            OperationComparisonOption(
                label="EXISTING CONTEXT",
                guidance=(
                    "Use mem embed. The parent stores only the Context identity; "
                    "the child Memories remain in the child, although recursive "
                    "operations may traverse them."
                ),
            ),
        ),
    ),
)


__all__ = ["ADD_DETAILS"]

"""The version choice and restoration contract exposed by Sync Help."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)

SYNC_DETAILS = (
    OperationComparisonDetail(
        id="conflict-version", operation="sync", title="CONFLICT VERSION",
        use_when="Both mem and external files changed differently since their last successful Sync.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Choose once for all supported content conflicts selected in this Profile. "
            "Documents changed on only one side keep their normal Sync direction. "
            "Both versions remain as checkpoints. Undo/Redo restores the entire Sync "
            "action, including the actual file versions from before/after Sync. "
            "Up/Down moves, Enter chooses, and Escape cancels without changing files. "
            "Unsupported composite, placement, or local-edit/external-deletion conflicts "
            "are refused without overwriting either side."
        ),
        options=(
            OperationComparisonOption(label="Use external files", guidance="Replace the conflicting mem content with the external file versions."),
            OperationComparisonOption(label="Use mem", guidance="Replace the conflicting external files with the current mem versions."),
        ),
    ),
)

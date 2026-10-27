"""The version choice and restoration contract exposed by Sync Help."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)

SYNC_DETAILS = (
    OperationComparisonDetail(
        id="conflict-version",
        operation="sync",
        title="CONFLICT VERSION",
        use_when="Both mem and external files changed differently since their last successful Sync.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Run mem sync without arguments to discover and synchronize all supported "
            "Markdown (.md) documents and owned Contexts in the active Profile's project folder, "
            "including subfolders. SKILL.md is ordinary Markdown. Block separator blank "
            "lines are normalized; syntax and block-internal content are retained. "
            "Existing exclusions and .memignore apply. "
            "Only the final .md is removed from each file's Context name; "
            "notes.md.md becomes notes.md. Unpaired Contexts use their name plus .md. "
            "Invalid file or folder names stop Sync; rename them to follow Context naming rules. "
            "Choose once for all supported content conflicts in this Profile. "
            "Documents changed on only one side keep their normal Sync direction. "
            "Up/Down moves, Enter chooses, and Escape cancels without changing files. "
            "Unsupported composite, placement, or local-edit/external-deletion conflicts "
            "are refused without overwriting either side."
        ),
        options=(
            OperationComparisonOption(
                label="Use workspace files",
                guidance="Replace the conflicting mem content with the external file versions.",
            ),
            OperationComparisonOption(
                label="Use mem",
                guidance="Replace the conflicting external files with the current mem versions.",
            ),
        ),
    ),
)

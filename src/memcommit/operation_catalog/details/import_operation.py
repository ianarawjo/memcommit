"""Detailed Help topics owned by Import."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


IMPORT_DETAILS = (
    OperationTextDetail(
        id="current-limitation",
        operation="import",
        title="CURRENT LIMITATION",
        use_when="Checking whether Import supports the intended external source.",
        discovery=DetailDiscovery.ON_DEMAND,
        detail_kind=HelpDetailKind.LIMITATION,
        body=(
            "mem import currently covers only MemCommit-to-MemCommit transfer, "
            "so its broader resource-import role is not yet complete. It accepts "
            "Profiles from an external .mem store or package, and Profiles, "
            "Context trees, or Memories from another registered Profile. "
            "It also accepts native Context JSON files or directories of "
            "context.json files, and standalone Memory JSON files. File imports "
            "preserve identities and reject unresolved external references or "
            "live Grant/query-only bindings. "
            "Plain-text files, arbitrary documents, Skills, and Export are "
            "planned resource kinds but are not yet implemented."
        ),
    ),
)


__all__ = ["IMPORT_DETAILS"]

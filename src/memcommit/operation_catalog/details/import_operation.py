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
            "Import accepts Profiles, Contexts and Memories from mem sources, plus "
            "UTF-8 Markdown, text, YAML and Agent Skills documents. Use "
            "mem import document --from PATH [--as NEW_ROOT] [-r]. Document imports "
            "create a new document or package Context beneath the current/--into "
            "parent, or at --as. Skill metadata is editable in its own Context; "
            "non-document skill files are retained without execution. "
            "Import applies syntax rules, not semantic atomization. Use mem export "
            "to write current results to a new directory. Native mem records "
            "preserve identities and reject open or authority-bearing references."
        ),
    ),
)


__all__ = ["IMPORT_DETAILS"]

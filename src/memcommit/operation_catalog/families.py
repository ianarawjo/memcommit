"""Stable families for the public MemCommit operation surface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class OperationFamilyId(str, Enum):
    """Stable, presentation-independent identity for one operation family."""

    BROWSE_NAVIGATE = "BROWSE_NAVIGATE"
    CREATE_COPY_CONNECT = "CREATE_COPY_CONNECT"
    SEARCH_EXPLAIN = "SEARCH_EXPLAIN"
    DIRECT_CHANGES = "DIRECT_CHANGES"
    SEMANTIC_UPDATES = "SEMANTIC_UPDATES"
    TRANSLATION = "TRANSLATION"
    QUALITY_RESOLUTION = "QUALITY_RESOLUTION"
    OPERATION_LIFECYCLE = "OPERATION_LIFECYCLE"
    GROUND_WORKBENCH = "GROUND_WORKBENCH"
    HISTORY_RECOVERY = "HISTORY_RECOVERY"
    PROFILES = "PROFILES"
    SHARING_PROTECTION = "SHARING_PROTECTION"
    SYSTEM_STUDY_TOOLS = "SYSTEM_STUDY_TOOLS"


class OperationFamilySectionId(str, Enum):
    """Stable identity for an intentional subdivision of one family."""

    SEARCH_RETRIEVE_ANSWER = "SEARCH_RETRIEVE_ANSWER"
    SEARCH_SYNTHESIZE = "SEARCH_SYNTHESIZE"
    SEMANTIC_UPDATE_FOUNDATION = "SEMANTIC_UPDATE_FOUNDATION"
    SEMANTIC_UPDATE_DERIVE = "SEMANTIC_UPDATE_DERIVE"
    SEMANTIC_UPDATE_CURATE_INTEGRATE = "SEMANTIC_UPDATE_CURATE_INTEGRATE"
    QUALITY_RESOLUTION_DIAGNOSE = "QUALITY_RESOLUTION_DIAGNOSE"
    QUALITY_RESOLUTION_REPAIR = "QUALITY_RESOLUTION_REPAIR"
    QUALITY_RESOLUTION_VALIDATE = "QUALITY_RESOLUTION_VALIDATE"
    HISTORY_INSPECTION = "HISTORY_INSPECTION"
    HISTORY_RECOVERY = "HISTORY_RECOVERY"


FamilyExecutionLabel = Literal["NO LLM", "LLM-BASED", "MIXED"]


@dataclass(frozen=True, slots=True)
class OperationFamilySection:
    """One ordered affordance section inside an operation family."""

    id: OperationFamilySectionId
    title: str
    operation_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, OperationFamilySectionId):
            raise TypeError("Operation family section must use a stable identity.")
        if not self.title.strip():
            raise ValueError("Operation family section title must be nonblank.")
        if not self.operation_names or any(
            not name.strip() for name in self.operation_names
        ):
            raise ValueError("Operation family section members must be nonblank.")
        if len(set(self.operation_names)) != len(self.operation_names):
            raise ValueError("Operation family section members must be unique.")


@dataclass(frozen=True, slots=True)
class OperationFamily:
    """One ordered family in MemCommit's public operation affordance."""

    id: OperationFamilyId
    title: str
    operation_names: tuple[str, ...]
    description: str
    execution_label: FamilyExecutionLabel | None
    sections: tuple[OperationFamilySection, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, OperationFamilyId):
            raise TypeError("Operation family must use a stable family identity.")
        if not self.title.strip() or not self.description.strip():
            raise ValueError("Operation family copy must be nonblank.")
        if not self.operation_names or any(
            not name.strip() for name in self.operation_names
        ):
            raise ValueError("Operation family members must be nonblank.")
        if len(set(self.operation_names)) != len(self.operation_names):
            raise ValueError("Operation family members must be unique.")
        if self.execution_label not in {None, "NO LLM", "LLM-BASED", "MIXED"}:
            raise ValueError("Operation family execution label is invalid.")
        if not isinstance(self.sections, tuple) or any(
            not isinstance(section, OperationFamilySection)
            for section in self.sections
        ):
            raise TypeError("Operation family sections must be an immutable tuple.")
        section_ids = [section.id for section in self.sections]
        section_titles = [section.title for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("Operation family section identities must be unique.")
        if len(section_titles) != len(set(section_titles)):
            raise ValueError("Operation family section titles must be unique.")
        if self.sections:
            # Sections are a complete ordered projection, not tags layered on
            # top of the family. Requiring exact flattening keeps application
            # and adapter groupings from silently losing or duplicating rows.
            section_members = tuple(
                operation_name
                for section in self.sections
                for operation_name in section.operation_names
            )
            if section_members != self.operation_names:
                raise ValueError(
                    "Operation family sections must exactly preserve family order."
                )


OPERATION_FAMILIES = (
    OperationFamily(
        id=OperationFamilyId.BROWSE_NAVIGATE,
        title="BROWSE & NAVIGATE",
        operation_names=(
            "status",
            "pwd",
            "contexts",
            "list",
            "show",
            "switch",
            "checkout",
            "rename",
        ),
        description=(
            "Inspect the current location and available Contexts, then move "
            "through the Context namespace."
        ),
        execution_label="NO LLM",
    ),
    OperationFamily(
        id=OperationFamilyId.CREATE_COPY_CONNECT,
        title="CREATE, COPY & CONNECT",
        operation_names=(
            "init",
            "add",
            "copy",
            "branch",
            "import",
            "reference",
            "embed",
        ),
        description=(
            "Create Contexts or Memories, copy or import resources, or connect "
            "existing material."
        ),
        execution_label="NO LLM",
    ),
    OperationFamily(
        id=OperationFamilyId.SEARCH_EXPLAIN,
        title="SEARCH & EXPLAIN",
        operation_names=("find", "search", "query", "summarize", "compare"),
        description=(
            "Find exact text directly, or use LLM-based semantic retrieval, "
            "answering, summarization, and comparison within the selected "
            "authorized scope."
        ),
        execution_label="MIXED",
        sections=(
            OperationFamilySection(
                id=OperationFamilySectionId.SEARCH_RETRIEVE_ANSWER,
                title="RETRIEVE & ANSWER",
                operation_names=("find", "search", "query"),
            ),
            OperationFamilySection(
                id=OperationFamilySectionId.SEARCH_SYNTHESIZE,
                title="SYNTHESIZE",
                operation_names=("summarize", "compare"),
            ),
        ),
    ),
    OperationFamily(
        id=OperationFamilyId.DIRECT_CHANGES,
        title="DIRECT CHANGES",
        operation_names=(
            "edit",
            "move",
            "replace",
            "chunk",
            "delete",
            "clear",
            "merge",
        ),
        description=(
            "Apply explicit inputs and reviewed choices through deterministic "
            "program logic to change content."
        ),
        execution_label="NO LLM",
    ),
    OperationFamily(
        id=OperationFamilyId.SEMANTIC_UPDATES,
        title="SEMANTIC UPDATES",
        operation_names=(
            "update",
            "atomize",
            "distill",
            "elaborate",
            "makemore",
            "forget",
            "sever",
            "meld",
        ),
        description=(
            "Use semantic decisions to update, derive, curate, or integrate "
            "content through operation-owned review and Apply boundaries."
        ),
        execution_label="LLM-BASED",
        sections=(
            OperationFamilySection(
                id=OperationFamilySectionId.SEMANTIC_UPDATE_FOUNDATION,
                title="FOUNDATION",
                operation_names=("update",),
            ),
            OperationFamilySection(
                id=OperationFamilySectionId.SEMANTIC_UPDATE_DERIVE,
                title="DERIVE",
                operation_names=("atomize", "distill", "elaborate", "makemore"),
            ),
            OperationFamilySection(
                id=OperationFamilySectionId.SEMANTIC_UPDATE_CURATE_INTEGRATE,
                title="CURATE & INTEGRATE",
                operation_names=("forget", "sever", "meld"),
            ),
        ),
    ),
    OperationFamily(
        id=OperationFamilyId.TRANSLATION,
        title="TRANSLATION",
        operation_names=("translate",),
        description=(
            "Create reusable language views or materializations while preserving "
            "the selected Source content."
        ),
        execution_label="LLM-BASED",
    ),
    OperationFamily(
        id=OperationFamilyId.QUALITY_RESOLUTION,
        title="QUALITY & RESOLUTION",
        operation_names=(
            "find-duplicates",
            "find-redundancies",
            "find-ambiguities",
            "find-conflicts",
            "audit",
            "dedup",
            "dedun",
            "resolve",
            "fit",
            "check-conformance",
        ),
        description=(
            "Diagnose quality issues, repair exact or semantic problems, and "
            "validate compatibility or rule conformance."
        ),
        execution_label="MIXED",
        sections=(
            OperationFamilySection(
                id=OperationFamilySectionId.QUALITY_RESOLUTION_DIAGNOSE,
                title="DIAGNOSE",
                operation_names=(
                    "find-duplicates",
                    "find-redundancies",
                    "find-ambiguities",
                    "find-conflicts",
                    "audit",
                ),
            ),
            OperationFamilySection(
                id=OperationFamilySectionId.QUALITY_RESOLUTION_REPAIR,
                title="REPAIR",
                operation_names=("dedup", "dedun", "resolve"),
            ),
            OperationFamilySection(
                id=OperationFamilySectionId.QUALITY_RESOLUTION_VALIDATE,
                title="VALIDATE",
                operation_names=("fit", "check-conformance"),
            ),
        ),
    ),
    OperationFamily(
        id=OperationFamilyId.OPERATION_LIFECYCLE,
        title="OPERATION LIFECYCLE",
        operation_names=("impact", "review"),
        description=(
            "Inspect a planned operation before Apply or examine retained "
            "evidence after execution."
        ),
        execution_label="MIXED",
    ),
    OperationFamily(
        id=OperationFamilyId.GROUND_WORKBENCH,
        title="GROUND WORKBENCH",
        operation_names=("ground",),
        description=(
            "Turn abstract ideas into reviewable common ground by developing a "
            "Goal, Rules, and example Memories together."
        ),
        execution_label="LLM-BASED",
    ),
    OperationFamily(
        id=OperationFamilyId.HISTORY_RECOVERY,
        title="HISTORY & RECOVERY",
        operation_names=(
            "log",
            "diff",
            "trace",
            "rationale",
            "checkpoint",
            "undo",
            "redo",
            "revert",
        ),
        description=(
            "Inspect provenance and recorded changes. Restore an earlier state "
            "through explicit history operations."
        ),
        execution_label="MIXED",
        sections=(
            OperationFamilySection(
                id=OperationFamilySectionId.HISTORY_INSPECTION,
                title="INSPECTION",
                operation_names=("log", "diff", "trace", "rationale"),
            ),
            OperationFamilySection(
                id=OperationFamilySectionId.HISTORY_RECOVERY,
                title="RECOVERY",
                operation_names=("checkpoint", "undo", "redo", "revert"),
            ),
        ),
    ),
    OperationFamily(
        id=OperationFamilyId.PROFILES,
        title="PROFILES",
        operation_names=("profile",),
        description=(
            "Select and administer complete local Profile stores and their "
            "managed names."
        ),
        execution_label="NO LLM",
    ),
    OperationFamily(
        id=OperationFamilyId.SHARING_PROTECTION,
        title="SHARING & PROTECTION",
        operation_names=("share", "lock", "unlock"),
        description=(
            "Deliver owned Contexts and protect Memory, Context, or Profile writes."
        ),
        execution_label="NO LLM",
    ),
    OperationFamily(
        id=OperationFamilyId.SYSTEM_STUDY_TOOLS,
        title="SYSTEM & STUDY TOOLS",
        operation_names=("help", "provider", "config", "init-study", "eval"),
        description=(
            "Configure MemCommit, prepare studies, and discover the reserved Eval surface."
        ),
        execution_label=None,
    ),
)


OPERATION_FAMILY_BY_ID = {family.id: family for family in OPERATION_FAMILIES}
OPERATION_FAMILY_BY_TITLE = {
    family.title: family for family in OPERATION_FAMILIES
}
OPERATION_FAMILY_BY_OPERATION = {
    operation_name: family
    for family in OPERATION_FAMILIES
    for operation_name in family.operation_names
}
OPERATION_FAMILY_SECTION_BY_ID = {
    section.id: section
    for family in OPERATION_FAMILIES
    for section in family.sections
}
OPERATION_FAMILY_SECTION_BY_OPERATION = {
    operation_name: section
    for family in OPERATION_FAMILIES
    for section in family.sections
    for operation_name in section.operation_names
}

if len(OPERATION_FAMILY_BY_ID) != len(OPERATION_FAMILIES):  # pragma: no cover
    raise RuntimeError("Operation family identities must be unique.")
if len(OPERATION_FAMILY_BY_TITLE) != len(OPERATION_FAMILIES):  # pragma: no cover
    raise RuntimeError("Operation family titles must be unique.")
if sum(len(family.operation_names) for family in OPERATION_FAMILIES) != len(
    OPERATION_FAMILY_BY_OPERATION
):  # pragma: no cover
    raise RuntimeError("One public operation cannot belong to two families.")
if sum(len(family.sections) for family in OPERATION_FAMILIES) != len(
    OPERATION_FAMILY_SECTION_BY_ID
):  # pragma: no cover
    raise RuntimeError("Operation family section identities must be globally unique.")
if sum(
    len(section.operation_names)
    for family in OPERATION_FAMILIES
    for section in family.sections
) != len(OPERATION_FAMILY_SECTION_BY_OPERATION):  # pragma: no cover
    raise RuntimeError("One public operation cannot belong to two family sections.")


def operation_family(operation_name: str) -> OperationFamily:
    """Return the stable family for one exact public operation name."""

    try:
        return OPERATION_FAMILY_BY_OPERATION[operation_name]
    except KeyError as error:
        raise KeyError(
            f"No operation family is registered for {operation_name!r}."
        ) from error


def operation_family_section(
    operation_name: str,
) -> OperationFamilySection | None:
    """Return an operation's optional section after validating its family."""

    operation_family(operation_name)
    return OPERATION_FAMILY_SECTION_BY_OPERATION.get(operation_name)


__all__ = [
    "FamilyExecutionLabel",
    "OPERATION_FAMILIES",
    "OPERATION_FAMILY_BY_ID",
    "OPERATION_FAMILY_BY_OPERATION",
    "OPERATION_FAMILY_BY_TITLE",
    "OPERATION_FAMILY_SECTION_BY_ID",
    "OPERATION_FAMILY_SECTION_BY_OPERATION",
    "OperationFamily",
    "OperationFamilyId",
    "OperationFamilySection",
    "OperationFamilySectionId",
    "operation_family",
    "operation_family_section",
]

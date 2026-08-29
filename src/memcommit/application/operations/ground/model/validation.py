"""Whole-session schema and relationship validation for Ground."""

from __future__ import annotations

from typing import TypeVar

from memcommit.application.operations.ground.contracts import (
    GroundError,
    validate_ground_contract_name,
)

from .records import (
    GROUND_LEGACY_SCHEMA_VERSION,
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GROUND_SCHEMA_VERSION,
    METHOD_REFERENCES,
    GroundBrief,
    GroundFrame,
    GroundItem,
    GroundReference,
    GroundSession,
    GroundTargetRequirement,
    _GROUND_STATUSES,
    _TARGET_FRAME_ROLES,
    _exact_dict,
    _integer,
    _string,
    _uuid,
)

_GroundSessionT = TypeVar("_GroundSessionT", bound=GroundSession)


def ground_session_from_dict(
    session_type: type[_GroundSessionT],
    value: object,
) -> _GroundSessionT:
    if not isinstance(value, dict):
        raise GroundError("Invalid grounding session.")
    schema_version = value.get("schema_version")
    if type(schema_version) is not int:
        raise GroundError("Unsupported grounding session schema version.")
    if schema_version == GROUND_LEGACY_SCHEMA_VERSION:
        return legacy_ground_session_from_dict(session_type, value)
    if schema_version not in {
        GROUND_SCHEMA_VERSION,
        GROUND_PROPOSITION_SCHEMA_VERSION,
    }:
        raise GroundError("Unsupported grounding session schema version.")

    data = _exact_dict(
        value,
        {
            "schema_version",
            "uid",
            "contract_name",
            "goal",
            "completion_criterion",
            "scope",
            "status",
            "revision",
            "items",
            "brief",
            "frames",
            "requirements",
            "cursor_position",
            "references",
        },
        "grounding session",
    )
    status = _string(
        data["status"],
        "grounding session status",
        limit=20,
    )
    scope = data["scope"]
    items = data["items"]
    frames = data["frames"]
    requirements = data["requirements"]
    references = data["references"]
    if (
        status not in _GROUND_STATUSES
        or not isinstance(scope, list)
        or len(scope) > 100
        or any(
            not isinstance(item, str) or not item.strip() or len(item) > 500
            for item in scope
        )
        or len(set(scope)) != len(scope)
        or not isinstance(items, list)
        or not isinstance(frames, list)
        or not isinstance(requirements, list)
        or not isinstance(references, list)
    ):
        raise GroundError("Invalid grounding session.")
    parsed_items = tuple(
        GroundItem.from_dict(
            item,
            schema_version=schema_version,
        )
        for item in items
    )
    parsed_frames = tuple(GroundFrame.from_dict(frame) for frame in frames)
    parsed_requirements = tuple(
        GroundTargetRequirement.from_dict(requirement) for requirement in requirements
    )
    parsed_references = tuple(
        GroundReference.from_dict(reference) for reference in references
    )
    item_uids = {item.uid for item in parsed_items}
    requirement_uids = {requirement.uid for requirement in parsed_requirements}
    if len(item_uids) != len(parsed_items):
        raise GroundError("Duplicate grounding item uid.")
    if item_uids & requirement_uids:
        raise GroundError("Grounding item and requirement uids overlap.")
    if any(
        related_uid not in item_uids | requirement_uids
        for item in parsed_items
        for related_uid in item.related_uids
    ):
        raise GroundError("Grounding item references an unknown item or requirement.")
    item_by_uid = {item.uid: item for item in parsed_items}
    for item in parsed_items:
        if item.kind == "RULE" and any(
            related_uid not in item_by_uid or item_by_uid[related_uid].kind != "CASE"
            for related_uid in item.related_uids
        ):
            raise GroundError("Grounding Rules may relate only to Ground Memories.")
        if item.kind == "CASE":
            valid_rule_links = all(
                related_uid in item_by_uid
                and item_by_uid[related_uid].kind == "RULE"
                and item.uid in item_by_uid[related_uid].related_uids
                for related_uid in item.related_uids
            )
            required_legacy_link = (
                schema_version != GROUND_SCHEMA_VERSION or len(item.related_uids) == 1
            )
            if not valid_rule_links or not required_legacy_link:
                raise GroundError(
                    "Ground Memory Rule links must be valid and reciprocal."
                )
        if item.kind == "RULE" and any(
            related_uid not in item_by_uid
            or item.uid not in item_by_uid[related_uid].related_uids
            for related_uid in item.related_uids
        ):
            raise GroundError("Grounding Rule/Memory links must be reciprocal.")
        if item.kind == "DECISION" and item.status != "RESOLVED":
            raise GroundError("Grounding decisions must be resolved.")
    for item in parsed_items:
        if item.kind in {"RULE", "CASE"} and item.status == "ACCEPTED":
            if item.origin != "JOINT" or not any(
                decision.kind == "DECISION"
                and decision.status == "RESOLVED"
                and decision.content == f"ACCEPT {item.kind}"
                and decision.origin == "USER"
                and decision.related_uids == (item.uid,)
                and decision.iteration == item.iteration
                for decision in parsed_items
            ):
                raise GroundError(
                    "An accepted grounding item requires its recorded "
                    "approval decision."
                )
    frame_uids = {frame.context_uid for frame in parsed_frames}
    frame_names = {frame.context_name for frame in parsed_frames}
    if (
        len(frame_uids) != len(parsed_frames)
        or len(frame_names) != len(parsed_frames)
        or sum(frame.role == "RAW_EVIDENCE" for frame in parsed_frames) != 1
        or sum(frame.role == "WORKING_CANDIDATES" for frame in parsed_frames) != 1
        or not any(frame.role in _TARGET_FRAME_ROLES for frame in parsed_frames)
    ):
        raise GroundError("Invalid grounding frame registry.")
    target_uids = {
        frame.context_uid
        for frame in parsed_frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    requirement_targets = {
        requirement.target_context_uid for requirement in parsed_requirements
    }
    if (
        len(requirement_uids) != len(parsed_requirements)
        or len(requirement_targets) != len(parsed_requirements)
        or requirement_targets != target_uids
    ):
        raise GroundError("Invalid grounding target requirements.")
    working_candidate_uids = {
        frame.context_uid
        for frame in parsed_frames
        if frame.role == "WORKING_CANDIDATES"
    }
    for item in parsed_items:
        if any(
            source_ref.context_uid not in working_candidate_uids
            for source_ref in item.source_refs
        ):
            raise GroundError(
                "Ground Memories must reference the bound working-candidate Context."
            )
        if any(
            target_uid not in target_uids for target_uid in item.target_context_uids
        ):
            raise GroundError("Ground Memory references an unbound target Context.")
    if len({reference.uid for reference in parsed_references}) != len(
        parsed_references
    ):
        raise GroundError("Duplicate grounding reference uid.")
    revision = _integer(data["revision"], "grounding session revision")
    if (
        any(item.iteration < 1 for item in parsed_items)
        or (revision == 0) != (not parsed_items)
        or (parsed_items and max(item.iteration for item in parsed_items) != revision)
    ):
        raise GroundError(
            "Grounding item iterations do not match the session revision."
        )
    if status != "OPEN":
        raise GroundError("Bound Ground schemas support only an OPEN workbench.")
    if parsed_references != METHOD_REFERENCES:
        raise GroundError("Bound Ground schema has invalid method references.")
    brief = GroundBrief.from_dict(data["brief"])
    cursor_position = _integer(
        data["cursor_position"],
        "grounding cursor position",
    )
    candidate_frame = next(
        frame for frame in parsed_frames if frame.role == "WORKING_CANDIDATES"
    )
    if (candidate_frame.direct_memory_count == 0 and cursor_position != 0) or (
        candidate_frame.direct_memory_count > 0
        and cursor_position >= candidate_frame.direct_memory_count
    ):
        raise GroundError("Invalid grounding cursor position.")
    return session_type(
        uid=_uuid(data["uid"], "grounding session uid"),
        contract_name=validate_ground_contract_name(
            data["contract_name"],
        ),
        goal=_string(
            data["goal"],
            "grounding goal",
            empty=True,
        ),
        completion_criterion=_string(
            data["completion_criterion"],
            "grounding completion criterion",
        ),
        scope=tuple(scope),
        status=status,
        revision=revision,
        items=parsed_items,
        references=parsed_references,
        schema_version=schema_version,
        brief=brief,
        frames=parsed_frames,
        requirements=parsed_requirements,
        cursor_position=cursor_position,
    )


def legacy_ground_session_from_dict(
    session_type: type[_GroundSessionT],
    value: object,
) -> _GroundSessionT:
    data = _exact_dict(
        value,
        {
            "schema_version",
            "uid",
            "contract_name",
            "goal",
            "completion_criterion",
            "scope",
            "status",
            "revision",
            "items",
            "references",
        },
        "grounding session",
    )
    status = _string(
        data["status"],
        "grounding session status",
        limit=20,
    )
    scope = data["scope"]
    items = data["items"]
    references = data["references"]
    if (
        status not in _GROUND_STATUSES
        or not isinstance(scope, list)
        or len(scope) > 100
        or any(
            not isinstance(item, str) or not item.strip() or len(item) > 500
            for item in scope
        )
        or len(set(scope)) != len(scope)
        or not isinstance(items, list)
        or not isinstance(references, list)
    ):
        raise GroundError("Invalid grounding session.")
    parsed_items = tuple(
        GroundItem.from_dict(
            item,
            schema_version=GROUND_LEGACY_SCHEMA_VERSION,
        )
        for item in items
    )
    parsed_references = tuple(
        GroundReference.from_dict(reference) for reference in references
    )
    item_uids = {item.uid for item in parsed_items}
    if len(item_uids) != len(parsed_items):
        raise GroundError("Duplicate grounding item uid.")
    if any(
        related_uid not in item_uids
        for item in parsed_items
        for related_uid in item.related_uids
    ):
        raise GroundError("Grounding item references an unknown item.")
    revision = _integer(data["revision"], "grounding session revision")
    if any(item.iteration > revision for item in parsed_items):
        raise GroundError("Grounding item exceeds the session revision.")
    # Version 1 deliberately remains empty-only. It can be upgraded only
    # through the explicit frame-binding action.
    if status != "OPEN" or revision != 0 or parsed_items:
        raise GroundError(
            "Grounding schema version 1 supports only an empty OPEN session."
        )
    if parsed_references != METHOD_REFERENCES:
        raise GroundError("Grounding schema version 1 has invalid method references.")
    return session_type(
        uid=_uuid(data["uid"], "grounding session uid"),
        contract_name=validate_ground_contract_name(
            data["contract_name"],
        ),
        goal=_string(
            data["goal"],
            "grounding goal",
            empty=True,
        ),
        completion_criterion=_string(
            data["completion_criterion"],
            "grounding completion criterion",
        ),
        scope=tuple(scope),
        status=status,
        revision=revision,
        items=parsed_items,
        references=parsed_references,
        schema_version=GROUND_LEGACY_SCHEMA_VERSION,
    )

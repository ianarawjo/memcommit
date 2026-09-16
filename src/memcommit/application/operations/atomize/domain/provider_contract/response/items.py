"""Read Memory classifications, split children, and literal source evidence."""

from __future__ import annotations

from ...model import (
    ATOMIZE_CHILD_CHAR_LIMIT,
    ATOMIZE_CHILD_LIMIT,
    ATOMIZE_CLASSIFICATIONS,
    ATOMIZE_REASON_CHAR_LIMIT,
    ATOMIZE_RULE_CODES,
    ATOMIZE_SOURCE_SPAN_LIMIT,
    AtomizeCandidate,
    AtomizeChild,
    AtomizeImpactError,
    AtomizeItem,
)
from .fields import _exact_dict, _short_string


def parse_items(
    values: object,
    candidates: list[AtomizeCandidate],
    declared_frames: dict[str, str] | None = None,
) -> tuple[AtomizeItem, ...]:
    declared_frames = declared_frames or {}
    if not isinstance(values, list) or len(values) != len(candidates):
        raise AtomizeImpactError(
            "Codex atomize impact did not classify every direct Memory exactly once."
        )

    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    parsed_by_id: dict[str, AtomizeItem] = {}
    for value in values:
        record = _exact_dict(
            value,
            {
                "candidate_id",
                "classification",
                "reason_codes",
                "children",
                "reason",
            },
        )
        candidate_id = record["candidate_id"]
        if (
            not isinstance(candidate_id, str)
            or candidate_id not in candidate_by_id
            or candidate_id in parsed_by_id
        ):
            raise AtomizeImpactError(
                "Codex atomize impact selected an unknown or duplicate "
                "Memory candidate."
            )
        candidate = candidate_by_id[candidate_id]

        classification = record["classification"]
        if (
            not isinstance(classification, str)
            or classification not in ATOMIZE_CLASSIFICATIONS
        ):
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid classification."
            )

        reason_codes = record["reason_codes"]
        if (
            not isinstance(reason_codes, list)
            or not reason_codes
            or len(reason_codes) > len(ATOMIZE_RULE_CODES)
            or any(
                not isinstance(code, str) or code not in ATOMIZE_RULE_CODES
                for code in reason_codes
            )
            or len(set(reason_codes)) != len(reason_codes)
        ):
            raise AtomizeImpactError(
                "Codex atomize impact returned invalid reason codes."
            )

        child_values = record["children"]
        if not isinstance(child_values, list):
            raise AtomizeImpactError(
                "Codex atomize impact returned invalid split children."
            )
        if classification == "COMPOSITE":
            if not 2 <= len(child_values) <= ATOMIZE_CHILD_LIMIT:
                raise AtomizeImpactError(
                    "Codex atomize impact returned an invalid composite split."
                )
        elif child_values:
            raise AtomizeImpactError(
                "Codex atomize impact returned children for a Memory that "
                "must remain unchanged."
            )

        children: list[AtomizeChild] = []
        for child_value in child_values:
            child = _exact_dict(
                child_value,
                {"content", "source_spans"},
            )
            content = _short_string(
                child["content"],
                label="child content",
                limit=ATOMIZE_CHILD_CHAR_LIMIT,
            )
            source_spans = child["source_spans"]
            declared_frame = declared_frames.get(
                candidate.memory.uid,
                "",
            )
            if (
                not isinstance(source_spans, list)
                or not 1 <= len(source_spans) <= ATOMIZE_SOURCE_SPAN_LIMIT
                or any(
                    not isinstance(span, str)
                    or not span.strip()
                    or len(span) > ATOMIZE_CHILD_CHAR_LIMIT
                    or (
                        span not in candidate.memory.content
                        and span not in declared_frame
                    )
                    for span in source_spans
                )
                or len(set(source_spans)) != len(source_spans)
            ):
                raise AtomizeImpactError(
                    "Codex atomize impact returned a child with invalid or "
                    "ungrounded source spans."
                )
            original_spans = tuple(
                span for span in source_spans if span in candidate.memory.content
            )
            frame_spans = tuple(
                span
                for span in source_spans
                if span not in candidate.memory.content and span in declared_frame
            )
            if not original_spans:
                raise AtomizeImpactError(
                    "Codex atomize impact returned a child without source "
                    "Memory evidence."
                )
            children.append(
                AtomizeChild(
                    content=content,
                    source_spans=original_spans,
                    frame_spans=frame_spans,
                )
            )

        reason = _short_string(
            record["reason"],
            label="reason",
            limit=ATOMIZE_REASON_CHAR_LIMIT,
        )
        parsed_by_id[candidate_id] = AtomizeItem(
            memory=candidate.memory,
            position=candidate.position,
            classification=classification,
            reason_codes=tuple(reason_codes),
            children=tuple(children),
            reason=reason,
            lint=candidate.lint,
        )

    if set(parsed_by_id) != set(candidate_by_id):
        raise AtomizeImpactError(
            "Codex atomize impact did not classify every direct Memory exactly once."
        )
    return tuple(
        parsed_by_id[candidate.candidate_id] for candidate in candidates
    )

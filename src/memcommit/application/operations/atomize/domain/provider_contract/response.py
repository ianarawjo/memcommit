"""Fail-closed Atomize response parsing, validation, and domain projection."""

from __future__ import annotations

import json

import re

from memcommit.application.capabilities.semantic.understanding import (
    UnderstandingError,
    UnderstandingSummary,
    parse_source_linked_understanding,
)

from ..model import (
    ATOMIZE_CHILD_CHAR_LIMIT,
    ATOMIZE_CHILD_LIMIT,
    ATOMIZE_CLASSIFICATIONS,
    ATOMIZE_CLARIFICATIONS,
    ATOMIZE_CONFLICTS,
    ATOMIZE_INTERPRETATIONS,
    ATOMIZE_OVERVIEW_CHAR_LIMIT,
    ATOMIZE_QUALITY_KINDS,
    ATOMIZE_QUALITY_READING_LIMIT,
    ATOMIZE_READING_LABEL_CHAR_LIMIT,
    ATOMIZE_READING_LABEL_WORD_LIMIT,
    ATOMIZE_REASON_CHAR_LIMIT,
    ATOMIZE_RESPONSE_CHAR_LIMIT,
    ATOMIZE_RULE_CODES,
    ATOMIZE_SCOPE_DIMENSIONS,
    ATOMIZE_SOURCE_SPAN_LIMIT,
    AtomizeCandidate,
    AtomizeChild,
    AtomizeImpactError,
    AtomizeItem,
    AtomizeOverview,
    AtomizeOverviewSection,
    AtomizeQualityIssue,
    AtomizeReading,
    _reading_roles,
)


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_dict(
    value: object,
    keys: set[str],
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise AtomizeImpactError(
            "Codex atomize impact returned invalid structured output."
        )
    return value


def _short_string(
    value: object,
    *,
    label: str,
    limit: int,
) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise AtomizeImpactError(f"Codex atomize impact returned an invalid {label}.")
    return value


def _parse_overview(
    value: object,
    candidate_by_id: dict[str, AtomizeCandidate],
) -> AtomizeOverview:
    record = _exact_dict(
        value,
        {"understood", "changed", "unresolved"},
    )

    source_uid_by_id = {
        candidate_id: candidate.memory.uid
        for candidate_id, candidate in candidate_by_id.items()
    }

    def deduplicate_source_ids(raw: object) -> object:
        """Normalize harmless duplicate citations unsupported by the schema."""

        if not isinstance(raw, dict):
            return raw
        source_ids = raw.get("source_ids")
        if not isinstance(source_ids, list) or any(
            not isinstance(candidate_id, str) for candidate_id in source_ids
        ):
            return raw
        normalized = dict(raw)
        normalized["source_ids"] = list(dict.fromkeys(source_ids))
        return normalized

    def parse_understood(raw: object) -> UnderstandingSummary:
        try:
            if (
                isinstance(raw, dict)
                and raw.get("text") == ""
                and raw.get("source_ids") == []
            ):
                return UnderstandingSummary(text="")
            return parse_source_linked_understanding(
                deduplicate_source_ids(raw),
                source_uid_by_id=source_uid_by_id,
                limit=ATOMIZE_OVERVIEW_CHAR_LIMIT,
            )
        except UnderstandingError as error:
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid source-linked "
                "natural-language report paragraph."
            ) from error

    def parse_section(raw: object) -> AtomizeOverviewSection:
        section = _exact_dict(raw, {"text", "source_ids"})
        raw_text = section["text"]
        source_ids = section["source_ids"]
        if (
            not isinstance(raw_text, str)
            or len(raw_text) > ATOMIZE_OVERVIEW_CHAR_LIMIT
            or not isinstance(source_ids, list)
            or any(
                not isinstance(candidate_id, str) or candidate_id not in candidate_by_id
                for candidate_id in source_ids
            )
        ):
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid source-linked overview."
            )
        # The provider's strict schema cannot use uniqueItems. Overview
        # citations have set semantics, so repeated aliases do not weaken the
        # evidence boundary and are retained once in first-seen order.
        source_ids = list(dict.fromkeys(source_ids))
        text = raw_text.strip()
        if text and (
            len(text.splitlines()) != 1
            or re.match(r"(?:[-*•]\s+|\d+[.)]\s+)", text) is not None
        ):
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid natural-language "
                "report paragraph."
            )
        text = " ".join(text.split())
        if text and not source_ids and candidate_by_id:
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid source-linked overview."
            )
        return AtomizeOverviewSection(
            text=text,
            source_uids=tuple(
                candidate_by_id[candidate_id].memory.uid for candidate_id in source_ids
            ),
        )

    return AtomizeOverview(
        understood=parse_understood(record["understood"]),
        changed=parse_section(record["changed"]),
        unresolved=parse_section(record["unresolved"]),
    )


def _parse_quality_issues(
    value: object,
    candidate_by_id: dict[str, AtomizeCandidate],
) -> tuple[AtomizeQualityIssue, ...]:
    if not isinstance(value, list):
        raise AtomizeImpactError(
            "Codex atomize impact returned invalid quality issues."
        )
    seen: set[str] = set()
    issues: list[AtomizeQualityIssue] = []
    for raw_issue in value:
        record = _exact_dict(
            raw_issue,
            {
                "kind",
                "source_ids",
                "interpretation",
                "clarification",
                "conflict",
                "ordinary_readings",
                "scope_dimensions",
                "reason",
                "question",
            },
        )
        kind = record["kind"]
        source_ids = record["source_ids"]
        interpretation = record["interpretation"]
        clarification = record["clarification"]
        conflict = record["conflict"]
        raw_readings = record["ordinary_readings"]
        scope_dimensions = record["scope_dimensions"]
        if (
            not isinstance(kind, str)
            or kind not in ATOMIZE_QUALITY_KINDS
            or not isinstance(source_ids, list)
            or any(
                not isinstance(candidate_id, str) or candidate_id not in candidate_by_id
                for candidate_id in source_ids
            )
            or len(set(source_ids)) != len(source_ids)
            or not isinstance(raw_readings, list)
            or len(raw_readings) > ATOMIZE_QUALITY_READING_LIMIT
            or not isinstance(scope_dimensions, list)
            or any(
                not isinstance(dimension, str)
                or dimension not in ATOMIZE_SCOPE_DIMENSIONS
                for dimension in scope_dimensions
            )
            or len(set(scope_dimensions)) != len(scope_dimensions)
        ):
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid quality issue."
            )
        reading_records: list[tuple[str, str]] = []
        seen_labels: set[str] = set()
        seen_texts: set[str] = set()
        for reading in raw_readings:
            reading_record = _exact_dict(reading, {"label", "text"})
            label = _short_string(
                reading_record["label"],
                label="ordinary reading label",
                limit=ATOMIZE_READING_LABEL_CHAR_LIMIT,
            )
            text = _short_string(
                reading_record["text"],
                label="ordinary reading text",
                limit=ATOMIZE_REASON_CHAR_LIMIT,
            )
            if (
                len(label.splitlines()) != 1
                or len(label.split()) > ATOMIZE_READING_LABEL_WORD_LIMIT
            ):
                raise AtomizeImpactError(
                    "Codex atomize impact returned an invalid ordinary reading label."
                )
            if label in seen_labels or text in seen_texts:
                raise AtomizeImpactError(
                    "Codex atomize impact returned duplicate ordinary "
                    "readings or labels."
                )
            seen_labels.add(label)
            seen_texts.add(text)
            reading_records.append((label, text))
        reason = _short_string(
            record["reason"],
            label="quality issue reason",
            limit=ATOMIZE_REASON_CHAR_LIMIT,
        )
        question = record["question"]
        if not isinstance(question, str) or len(question) > 500:
            raise AtomizeImpactError(
                "Codex atomize impact returned an invalid clarification question."
            )

        ordered_source_ids = sorted(
            source_ids,
            key=lambda candidate_id: candidate_by_id[candidate_id].position,
        )
        source_uids = tuple(
            candidate_by_id[candidate_id].memory.uid
            for candidate_id in ordered_source_ids
        )
        if kind == "AMBIGUITY":
            if (
                len(source_uids) != 1
                or not isinstance(interpretation, str)
                or interpretation not in ATOMIZE_INTERPRETATIONS
                or not isinstance(clarification, str)
                or clarification not in ATOMIZE_CLARIFICATIONS
                or conflict != "NONE"
                or scope_dimensions
                or (interpretation == "SINGLE" and len(reading_records) != 1)
                or (interpretation != "SINGLE" and len(reading_records) < 2)
                or (interpretation == "SINGLE" and clarification == "NONE")
                or (clarification == "NONE" and question.strip())
                or (clarification != "NONE" and not question.strip())
            ):
                raise AtomizeImpactError(
                    "Codex atomize impact returned an invalid ambiguity issue."
                )
            uid = f"ambiguity:{source_uids[0]}"
            roles = _reading_roles(
                interpretation,
                len(reading_records),
            )
            readings = tuple(
                AtomizeReading(
                    uid=f"{uid}:reading:{index}",
                    role=role,
                    label=label,
                    text=text,
                )
                for index, (role, (label, text)) in enumerate(
                    zip(roles, reading_records, strict=True),
                    start=1,
                )
            )
            issue = AtomizeQualityIssue(
                uid=uid,
                kind="AMBIGUITY",
                source_uids=source_uids,
                interpretation=interpretation,
                clarification=clarification,
                conflict=None,
                readings=readings,
                scope_dimensions=(),
                reason=reason,
                question=question.strip(),
            )
        else:
            if (
                len(source_uids) != 2
                or interpretation != "NONE"
                or clarification != "REQUIRED"
                or conflict not in ATOMIZE_CONFLICTS
                or (
                    conflict == "MAY"
                    and (
                        not scope_dimensions
                        or len(reading_records) < 2
                        or not question.strip()
                    )
                )
            ):
                raise AtomizeImpactError(
                    "Codex atomize impact returned an invalid conflict issue."
                )
            uid = f"conflict:{source_uids[0]}:{source_uids[1]}"
            readings = tuple(
                AtomizeReading(
                    uid=f"{uid}:reading:{index}",
                    role="COMPETING",
                    label=label,
                    text=text,
                )
                for index, (label, text) in enumerate(
                    reading_records,
                    start=1,
                )
            )
            issue = AtomizeQualityIssue(
                uid=uid,
                kind="CONFLICT",
                source_uids=source_uids,
                interpretation=None,
                clarification=None,
                conflict=conflict,
                readings=readings,
                scope_dimensions=tuple(scope_dimensions),
                reason=reason,
                question=question.strip(),
            )
        if issue.uid in seen:
            raise AtomizeImpactError(
                "Codex atomize impact returned a duplicate quality issue."
            )
        # Round-trip through the durable validator before accepting provider
        # semantics into the saved workbench artifact.
        issue = AtomizeQualityIssue.from_dict(issue.to_dict())
        seen.add(issue.uid)
        issues.append(issue)

    def issue_key(issue: AtomizeQualityIssue) -> tuple[int, int, str]:
        positions = [
            next(
                candidate.position
                for candidate in candidate_by_id.values()
                if candidate.memory.uid == source_uid
            )
            for source_uid in issue.source_uids
        ]
        return (
            min(positions),
            0 if issue.kind == "AMBIGUITY" else 1,
            issue.uid,
        )

    return tuple(sorted(issues, key=issue_key))


def _parse_items(
    raw: object,
    candidates: list[AtomizeCandidate],
    declared_frames: dict[str, str] | None = None,
) -> tuple[
    tuple[AtomizeItem, ...],
    AtomizeOverview,
    tuple[AtomizeQualityIssue, ...],
]:
    declared_frames = declared_frames or {}
    if (
        not isinstance(raw, str)
        or not raw.strip()
        or len(raw) > ATOMIZE_RESPONSE_CHAR_LIMIT
    ):
        raise AtomizeImpactError(
            "Codex atomize impact returned invalid structured output."
        )
    try:
        data = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise AtomizeImpactError(
            "Codex atomize impact returned invalid structured output."
        ) from error

    envelope = _exact_dict(
        data,
        {"overview", "items", "quality_issues"},
    )
    values = envelope["items"]
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
    parsed_items = tuple(
        parsed_by_id[candidate.candidate_id] for candidate in candidates
    )
    return (
        parsed_items,
        _parse_overview(envelope["overview"], candidate_by_id),
        _parse_quality_issues(
            envelope["quality_issues"],
            candidate_by_id,
        ),
    )

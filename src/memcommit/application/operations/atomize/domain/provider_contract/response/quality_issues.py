"""Read and validate Atomize ambiguity and conflict findings."""

from __future__ import annotations

from ...model import (
    ATOMIZE_CLARIFICATIONS,
    ATOMIZE_CONFLICTS,
    ATOMIZE_INTERPRETATIONS,
    ATOMIZE_QUALITY_KINDS,
    ATOMIZE_QUALITY_READING_LIMIT,
    ATOMIZE_READING_LABEL_CHAR_LIMIT,
    ATOMIZE_READING_LABEL_WORD_LIMIT,
    ATOMIZE_REASON_CHAR_LIMIT,
    ATOMIZE_SCOPE_DIMENSIONS,
    AtomizeCandidate,
    AtomizeImpactError,
    AtomizeQualityIssue,
    AtomizeReading,
    _reading_roles,
)
from .fields import _exact_dict, _short_string


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

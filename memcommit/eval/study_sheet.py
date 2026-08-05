"""Build a language-paired spreadsheet specification from study fixtures.

The Google Sheet is a review surface, not another Memory authority.  This
module therefore derives every row from the strict fixture loader and keeps
designer-only fields (verification, purpose, audience, relations, and update
patches) outside the Memory body.  A renderer can consume the emitted JSON
without reparsing the Markdown authoring format.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable, Mapping

from memcommit.eval.study_fixtures import (
    AudienceRole,
    FixtureDataset,
    FixtureMemory,
    STUDY_FIXTURE_SPECS,
    default_fixture_root,
    load_study_fixture_corpus,
    pair_fixture_translations,
)


SHEET_SPEC_SCHEMA_VERSION = 1
_LANGUAGE_ORDER = ("ko", "en")
_AUDIENCE_ORDER = (
    AudienceRole.ALL,
    AudienceRole.VISITOR,
    AudienceRole.STUDENT,
    AudienceRole.STAFF,
    AudienceRole.CONSTRUCTION_FACILITIES,
)


class StudySheetError(ValueError):
    """The review workbook cannot be derived without guessing."""


@dataclass(frozen=True)
class SheetColumn:
    """One stable workbook column and its requested presentation width."""

    key: str
    label: str
    width: int
    checkbox: bool = False
    tone: str | None = None


@dataclass(frozen=True)
class StudySheet:
    """One compact two-row-header data sheet."""

    name: str
    title: str
    language: str
    dataset: str
    query_only: bool
    columns: tuple[SheetColumn, ...]
    rows: tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class StudyWorkbookSpec:
    """All workbook data needed by the artifact renderer."""

    schema_version: int
    canonical_language: str
    translation_language: str
    ordinary_count: int
    query_only_count: int
    total_count: int
    sheets: tuple[StudySheet, ...]


_TAB_NAMES: Mapping[str, str] = {
    "task1-construction-updates": "T1 updates",
    "task1-campus-wiki": "T1 wiki",
    "task1-campus-wiki-details": "T1 details",
    "task2-advisor1": "T2 advisor1",
    "task2-advisor2": "T2 advisor2",
    "task2-proposal-guidelines": "T2 guidelines",
    "task3-personal-memory": "T3 personal",
    "task3-guardrails": "T3 guardrails",
    "task3-healthcare-qna": "T3 healthcare Q&A",
    "task3-healthcare-public-guidance": "T3 public guidance",
}


def _labels(language: str) -> dict[str, str]:
    if language == "ko":
        return {
            "verified": "Verified",
            "fixture_id": "Fixture ID",
            "location": "Memory / 업데이트 위치",
            "all": "전",
            "visitor": "방",
            "student": "학",
            "staff": "교",
            "operations": "관",
            "purpose": "목적",
            "content": "본문",
            "target_location": "대상 위치",
            "target_memory": "대상 Memory",
            "operation": "작업",
            "update_detail": "실제 변경",
            "before": "− 기존",
            "after": "+ 변경 후",
            "relation": "Relation band",
            "counterparts": "Paired fixture(s)",
            "section": "분류",
            "storage": "저장 경계",
            "source": "원본 파일",
            "query_only": "질의 전용",
            "ordinary": "일반 Context",
        }
    return {
        "verified": "Verified",
        "fixture_id": "Fixture ID",
        "location": "Memory / update location",
        "all": "All",
        "visitor": "Visitor",
        "student": "Student",
        "staff": "Staff",
        "operations": "C/F",
        "purpose": "Purpose",
        "content": "Content",
        "target_location": "Target location",
        "target_memory": "Target Memory",
        "operation": "Action",
        "update_detail": "Actual change",
        "before": "− Before",
        "after": "+ After",
        "relation": "Relation band",
        "counterparts": "Paired fixture(s)",
        "section": "Section",
        "storage": "Storage boundary",
        "source": "Source file",
        "query_only": "Query-only",
        "ordinary": "Ordinary Context",
    }


def _read_tsv(path: Path) -> tuple[dict[str, str], ...]:
    if not path.is_file():
        raise StudySheetError(f"Missing spreadsheet sidecar: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t", strict=True)
        if reader.fieldnames is None:
            raise StudySheetError(f"Missing TSV header: {path}")
        rows = tuple(dict(row) for row in reader)
    if not rows:
        raise StudySheetError(f"Empty spreadsheet sidecar: {path}")
    return rows


def _source_file(record: FixtureMemory) -> str:
    return f"{record.source_path.parent.name}/{record.source_path.name}"


def _section(record: FixtureMemory) -> str:
    parts = record.canonical_locator.split("/")
    if record.dataset in {
        "task3-healthcare-qna",
        "task3-healthcare-public-guidance",
    }:
        root_len = 3
    else:
        root_len = 1
    return parts[root_len] if len(parts) > root_len else "(root)"


def _audience_values(record: FixtureMemory) -> tuple[bool, ...]:
    present = set(record.audiences)
    return tuple(role in present for role in _AUDIENCE_ORDER)


def _base_columns(language: str) -> tuple[SheetColumn, ...]:
    label = _labels(language)
    return (
        SheetColumn("verified", label["verified"], 10, checkbox=True),
        SheetColumn("fixture_id", label["fixture_id"], 14),
        SheetColumn("section", label["section"], 20),
        SheetColumn("purpose", label["purpose"], 9),
        SheetColumn("location", label["location"], 34),
        SheetColumn("content", label["content"], 68),
    )


def _task1_columns(
    language: str,
    *,
    include_actions: bool,
) -> tuple[SheetColumn, ...]:
    label = _labels(language)
    columns = (
        SheetColumn("verified", label["verified"], 10, checkbox=True),
        SheetColumn("fixture_id", label["fixture_id"], 14),
        SheetColumn("location", label["location"], 36),
        SheetColumn("all", label["all"], 6, checkbox=True),
        SheetColumn("visitor", label["visitor"], 6, checkbox=True),
        SheetColumn("student", label["student"], 6, checkbox=True),
        SheetColumn("staff", label["staff"], 6, checkbox=True),
        SheetColumn("operations", label["operations"], 6, checkbox=True),
        SheetColumn("purpose", label["purpose"], 9),
        SheetColumn("content", label["content"], 68),
    )
    if not include_actions:
        return columns + (
            SheetColumn("storage", label["storage"], 16),
            SheetColumn("source", label["source"], 30),
        )
    return columns + (
        SheetColumn("target_location", label["target_location"], 34),
        SheetColumn("target_memory", label["target_memory"], 18),
        SheetColumn("operation", label["operation"], 10),
        SheetColumn("update_detail", label["update_detail"], 46),
        SheetColumn("before", label["before"], 54, tone="removed"),
        SheetColumn("after", label["after"], 54, tone="added"),
        SheetColumn("source", label["source"], 30),
    )


def _index_actions(
    fixture_root: Path,
    language: str,
) -> dict[str, tuple[dict[str, str], ...]]:
    path = fixture_root / language / f"task-1-update-actions-{language}.tsv"
    by_source: dict[str, list[dict[str, str]]] = {}
    for row in _read_tsv(path):
        source = row.get("source_id")
        if not source:
            raise StudySheetError(f"Missing source_id in {path}")
        by_source.setdefault(source, []).append(row)
    return {key: tuple(value) for key, value in by_source.items()}


def _join_actions(
    actions: Iterable[dict[str, str]],
    key: str,
) -> str:
    values = [row.get(key, "").strip() for row in actions]
    if any(not value for value in values):
        raise StudySheetError(f"Missing {key!r} in Task 1 update sidecar.")
    return "\n".join(values)


def _task1_rows(
    dataset: FixtureDataset,
    *,
    language: str,
    fixture_root: Path,
    include_actions: bool,
) -> tuple[tuple[object, ...], ...]:
    label = _labels(language)
    actions = _index_actions(fixture_root, language) if include_actions else {}
    rows: list[tuple[object, ...]] = []
    for record in dataset.records:
        prefix: tuple[object, ...] = (
            bool(record.verified),
            record.fixture_id or "",
            record.canonical_locator,
            *_audience_values(record),
            record.purpose,
            record.content,
        )
        if not include_actions:
            rows.append(
                prefix
                + (
                    label["query_only"] if dataset.spec.query_only else label["ordinary"],
                    _source_file(record),
                )
            )
            continue
        if record.fixture_id not in actions:
            raise StudySheetError(
                f"Task 1 update {record.fixture_id!r} has no action row."
            )
        source_actions = actions[record.fixture_id]
        rows.append(
            prefix
            + (
                _join_actions(source_actions, "target_location"),
                _join_actions(source_actions, "target_memory"),
                _join_actions(source_actions, "operation"),
                _join_actions(source_actions, "update_detail"),
                _join_actions(source_actions, "before_text"),
                _join_actions(source_actions, "after_text"),
                _source_file(record),
            )
        )
    return tuple(rows)


def _index_relations(
    fixture_root: Path,
    language: str,
) -> dict[str, tuple[str, str]]:
    path = fixture_root / language / f"task-2-pair-relations-{language}.tsv"
    result: dict[str, tuple[str, str]] = {}
    for row in _read_tsv(path):
        band = row.get("relationship_band", "").strip()
        left = tuple(
            item for item in row.get("left_fixture_ids", "").split(";") if item
        )
        right = tuple(
            item for item in row.get("right_fixture_ids", "").split(";") if item
        )
        if not band or not left or not right:
            raise StudySheetError(f"Invalid Task 2 relation row in {path}")
        for fixture_id in left:
            if fixture_id in result:
                raise StudySheetError(f"Duplicate relation member {fixture_id}")
            result[fixture_id] = (band, "; ".join(right))
        for fixture_id in right:
            if fixture_id in result:
                raise StudySheetError(f"Duplicate relation member {fixture_id}")
            result[fixture_id] = (band, "; ".join(left))
    return result


def _task2_rows(
    dataset: FixtureDataset,
    *,
    language: str,
    fixture_root: Path,
) -> tuple[tuple[object, ...], ...]:
    relations = (
        _index_relations(fixture_root, language)
        if dataset.spec.name in {"task2-advisor1", "task2-advisor2"}
        else {}
    )
    label = _labels(language)
    rows: list[tuple[object, ...]] = []
    for record in dataset.records:
        relation = relations.get(record.fixture_id or "", ("", ""))
        rows.append(
            (
                bool(record.verified),
                record.fixture_id or "",
                _section(record),
                record.purpose,
                record.canonical_locator,
                record.content,
                relation[0],
                relation[1],
                label["query_only"] if dataset.spec.query_only else label["ordinary"],
                _source_file(record),
            )
        )
    return tuple(rows)


def _task2_columns(
    language: str,
    *,
    include_relations: bool,
) -> tuple[SheetColumn, ...]:
    label = _labels(language)
    relation_columns = (
        SheetColumn("relation", label["relation"], 24),
        SheetColumn("counterparts", label["counterparts"], 25),
    ) if include_relations else ()
    return _base_columns(language) + relation_columns + (
        SheetColumn("storage", label["storage"], 16),
        SheetColumn("source", label["source"], 30),
    )


def _task3_rows(
    dataset: FixtureDataset,
    *,
    language: str,
) -> tuple[tuple[object, ...], ...]:
    label = _labels(language)
    return tuple(
        (
            bool(record.verified),
            _section(record),
            record.purpose,
            record.canonical_locator,
            record.content,
            label["query_only"] if dataset.spec.query_only else label["ordinary"],
            _source_file(record),
        )
        for record in dataset.records
    )


def _task3_columns(language: str) -> tuple[SheetColumn, ...]:
    label = _labels(language)
    return (
        SheetColumn("verified", label["verified"], 10, checkbox=True),
        SheetColumn("section", label["section"], 20),
        SheetColumn("purpose", label["purpose"], 9),
        SheetColumn("location", label["location"], 38),
        SheetColumn("content", label["content"], 72),
        SheetColumn("storage", label["storage"], 16),
        SheetColumn("source", label["source"], 30),
    )


def build_study_workbook_spec(
    fixture_root: Path | None = None,
) -> StudyWorkbookSpec:
    """Return the fully paired bilingual data specification."""

    root = fixture_root or default_fixture_root()
    corpora = {
        language: load_study_fixture_corpus(language=language, root=root)
        for language in _LANGUAGE_ORDER
    }
    ko_by_name = corpora["ko"].by_name()
    en_by_name = corpora["en"].by_name()
    for name in STUDY_FIXTURE_SPECS:
        pair_fixture_translations(en_by_name[name], ko_by_name[name])

    sheets: list[StudySheet] = []
    for dataset_name in STUDY_FIXTURE_SPECS:
        for language in _LANGUAGE_ORDER:
            dataset = corpora[language].by_name()[dataset_name]
            if dataset.spec.task == 1:
                include_actions = dataset_name == "task1-construction-updates"
                columns = _task1_columns(
                    language,
                    include_actions=include_actions,
                )
                rows = _task1_rows(
                    dataset,
                    language=language,
                    fixture_root=root,
                    include_actions=include_actions,
                )
            elif dataset.spec.task == 2:
                include_relations = dataset_name in {
                    "task2-advisor1",
                    "task2-advisor2",
                }
                columns = _task2_columns(
                    language,
                    include_relations=include_relations,
                )
                rows = _task2_rows(
                    dataset,
                    language=language,
                    fixture_root=root,
                )
                if not include_relations:
                    rows = tuple(
                        row[:6] + row[8:]
                        for row in rows
                    )
            else:
                columns = _task3_columns(language)
                rows = _task3_rows(dataset, language=language)
            language_label = language.upper()
            sheets.append(
                StudySheet(
                    name=f"{_TAB_NAMES[dataset_name]} · {language_label}",
                    title=(
                        f"Task {dataset.spec.task} · {dataset.spec.context_name} · "
                        f"{len(rows)} Memories · ✓ "
                        f"{sum(bool(record.verified) for record in dataset.records)}/"
                        f"{len(rows)}"
                    ),
                    language=language,
                    dataset=dataset_name,
                    query_only=dataset.spec.query_only,
                    columns=columns,
                    rows=rows,
                )
            )

    ordinary_count = sum(
        spec.expected_count
        for spec in STUDY_FIXTURE_SPECS.values()
        if not spec.query_only
    )
    query_count = sum(
        spec.expected_count
        for spec in STUDY_FIXTURE_SPECS.values()
        if spec.query_only
    )
    return StudyWorkbookSpec(
        schema_version=SHEET_SPEC_SCHEMA_VERSION,
        canonical_language="en",
        translation_language="ko",
        ordinary_count=ordinary_count,
        query_only_count=query_count,
        total_count=ordinary_count + query_count,
        sheets=tuple(sheets),
    )


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit the validated bilingual study workbook data spec."
    )
    parser.add_argument("--fixture-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spec = build_study_workbook_spec(args.fixture_root)
    payload = json.dumps(asdict(spec), ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

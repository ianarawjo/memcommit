"""Strict loaders for the human-reviewed Task 1--3 study fixtures.

The Markdown files are authoring artifacts, not a storage format.  This
module provides the narrow, validated boundary that a later fixture builder
can use without teaching that builder about three different Markdown shapes.
It deliberately keeps Memory content separate from designer-only metadata.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping


PURPOSE_CODES = frozenset({"KB", "PP", "SM", "UM", "WM", "OM"})
EXPECTED_CORPUS_COUNT = 1_306
_PURPOSE_NAMES = {
    "Knowledge Base": "KB",
    "Procedural Policy": "PP",
    "Self Model": "SM",
    "User Model": "UM",
    "World Model": "WM",
    "Other Model": "OM",
}


class StudyFixtureError(ValueError):
    """Raised when a fixture cannot be interpreted without guessing."""


class FixtureSyntax(str, Enum):
    """The three record shapes currently used by the study corpus."""

    TASK1_BLOCK = "task1-block"
    TASK2_INLINE = "task2-inline"
    TASK3_INLINE = "task3-inline"


class PurposeSidecarKey(str, Enum):
    """Stable key used by a task-level purpose sidecar."""

    FIXTURE_ID = "fixture-id"
    CANONICAL_LOCATOR = "canonical-locator"


class AudienceRole(str, Enum):
    """Language-neutral forms of the Task 1 audience annotations."""

    ALL = "all"
    VISITOR = "visitor"
    STUDENT = "student"
    STAFF = "staff"
    CONSTRUCTION_FACILITIES = "construction-facilities"


@dataclass(frozen=True)
class StudyFixtureSpec:
    """Static contract for one Markdown dataset and its purpose sidecar."""

    name: str
    task: int
    file_stem: str
    expected_count: int
    syntax: FixtureSyntax
    context_name: str
    purpose_sidecar_stem: str
    purpose_sidecar_count: int
    purpose_sidecar_key: PurposeSidecarKey
    sidecar_prefix: str
    fixture_ids_required: bool
    query_only: bool = False


@dataclass(frozen=True)
class FixtureMemory:
    """One Memory candidate plus non-content review metadata."""

    dataset: str
    language: str
    fixture_id: str | None
    locator: str
    canonical_locator: str
    content: str
    purpose: str
    audiences: tuple[AudienceRole, ...]
    verified: bool | None
    source_path: Path
    source_line: int

    @property
    def identity_key(self) -> str:
        """Return the stable per-dataset identity used for language pairing."""

        return self.fixture_id or self.canonical_locator


@dataclass(frozen=True)
class FixtureDataset:
    """A fully validated fixture dataset in one language."""

    spec: StudyFixtureSpec
    language: str
    records: tuple[FixtureMemory, ...]

    def by_locator(self) -> dict[str, FixtureMemory]:
        return {record.canonical_locator: record for record in self.records}

    def by_identity(self) -> dict[str, FixtureMemory]:
        return {record.identity_key: record for record in self.records}


@dataclass(frozen=True)
class FixtureCorpus:
    """All nine Task 1--3 datasets in one language."""

    language: str
    datasets: tuple[FixtureDataset, ...]

    @property
    def records(self) -> tuple[FixtureMemory, ...]:
        return tuple(
            record
            for dataset in self.datasets
            for record in dataset.records
        )

    def by_name(self) -> dict[str, FixtureDataset]:
        return {dataset.spec.name: dataset for dataset in self.datasets}


@dataclass(frozen=True)
class FixtureTranslationPair:
    """The same reviewed Memory identity in two language datasets."""

    canonical: FixtureMemory
    translation: FixtureMemory

    @property
    def uid_key(self) -> str:
        """Seed a builder can map to one UID and reuse in both Contexts."""

        return f"{self.canonical.dataset}:{self.canonical.identity_key}"


STUDY_FIXTURE_SPECS: Mapping[str, StudyFixtureSpec] = {
    "task1-description": StudyFixtureSpec(
        name="task1-description",
        task=1,
        file_stem="task-1-description",
        expected_count=1,
        syntax=FixtureSyntax.TASK2_INLINE,
        context_name="description",
        purpose_sidecar_stem="task-1-memory-purpose",
        purpose_sidecar_count=454,
        purpose_sidecar_key=PurposeSidecarKey.FIXTURE_ID,
        sidecar_prefix="T1-D-",
        fixture_ids_required=True,
    ),
    "task1-construction-updates": StudyFixtureSpec(
        name="task1-construction-updates",
        task=1,
        file_stem="task-1-construction-updates",
        expected_count=75,
        syntax=FixtureSyntax.TASK1_BLOCK,
        context_name="construction-updates",
        purpose_sidecar_stem="task-1-memory-purpose",
        purpose_sidecar_count=454,
        purpose_sidecar_key=PurposeSidecarKey.FIXTURE_ID,
        sidecar_prefix="T1-U-",
        fixture_ids_required=True,
    ),
    "task1-campus-wiki": StudyFixtureSpec(
        name="task1-campus-wiki",
        task=1,
        file_stem="task-1-campus-baseline",
        expected_count=300,
        syntax=FixtureSyntax.TASK1_BLOCK,
        context_name="campus-wiki",
        purpose_sidecar_stem="task-1-memory-purpose",
        purpose_sidecar_count=454,
        purpose_sidecar_key=PurposeSidecarKey.FIXTURE_ID,
        sidecar_prefix="T1-W-",
        fixture_ids_required=True,
    ),
    "task1-campus-wiki-details": StudyFixtureSpec(
        name="task1-campus-wiki-details",
        task=1,
        file_stem="task-1-campus-wiki-construction-details",
        expected_count=78,
        syntax=FixtureSyntax.TASK1_BLOCK,
        context_name="campus-wiki",
        purpose_sidecar_stem="task-1-memory-purpose",
        purpose_sidecar_count=454,
        purpose_sidecar_key=PurposeSidecarKey.FIXTURE_ID,
        sidecar_prefix="T1-Q-",
        fixture_ids_required=True,
        query_only=True,
    ),
    "task2-description": StudyFixtureSpec(
        name="task2-description",
        task=2,
        file_stem="task-2-description",
        expected_count=1,
        syntax=FixtureSyntax.TASK2_INLINE,
        context_name="description",
        purpose_sidecar_stem="task-2-memory-purpose",
        purpose_sidecar_count=376,
        purpose_sidecar_key=PurposeSidecarKey.FIXTURE_ID,
        sidecar_prefix="T2-D-",
        fixture_ids_required=True,
    ),
    "task2-advisor1": StudyFixtureSpec(
        name="task2-advisor1",
        task=2,
        file_stem="task-2-advisor1",
        expected_count=150,
        syntax=FixtureSyntax.TASK2_INLINE,
        context_name="advisor1",
        purpose_sidecar_stem="task-2-memory-purpose",
        purpose_sidecar_count=376,
        purpose_sidecar_key=PurposeSidecarKey.FIXTURE_ID,
        sidecar_prefix="T2-L-",
        fixture_ids_required=True,
    ),
    "task2-advisor2": StudyFixtureSpec(
        name="task2-advisor2",
        task=2,
        file_stem="task-2-advisor2",
        expected_count=150,
        syntax=FixtureSyntax.TASK2_INLINE,
        context_name="advisor2",
        purpose_sidecar_stem="task-2-memory-purpose",
        purpose_sidecar_count=376,
        purpose_sidecar_key=PurposeSidecarKey.FIXTURE_ID,
        sidecar_prefix="T2-R-",
        fixture_ids_required=True,
    ),
    "task2-proposal-guidelines": StudyFixtureSpec(
        name="task2-proposal-guidelines",
        task=2,
        file_stem="task-2-proposal-submission-guidelines",
        expected_count=75,
        syntax=FixtureSyntax.TASK2_INLINE,
        context_name="proposal-submission-guidelines",
        purpose_sidecar_stem="task-2-memory-purpose",
        purpose_sidecar_count=376,
        purpose_sidecar_key=PurposeSidecarKey.FIXTURE_ID,
        sidecar_prefix="T2-Q-",
        fixture_ids_required=True,
        query_only=True,
    ),
    "task3-description": StudyFixtureSpec(
        name="task3-description",
        task=3,
        file_stem="task-3-description",
        expected_count=1,
        syntax=FixtureSyntax.TASK3_INLINE,
        context_name="description",
        purpose_sidecar_stem="task-3-memory-purpose",
        purpose_sidecar_count=476,
        purpose_sidecar_key=PurposeSidecarKey.CANONICAL_LOCATOR,
        sidecar_prefix="description/",
        fixture_ids_required=False,
    ),
    "task3-personal-memory": StudyFixtureSpec(
        name="task3-personal-memory",
        task=3,
        file_stem="task-3-personal-memory",
        expected_count=300,
        syntax=FixtureSyntax.TASK3_INLINE,
        context_name="local/personal-memory",
        purpose_sidecar_stem="task-3-memory-purpose",
        purpose_sidecar_count=476,
        purpose_sidecar_key=PurposeSidecarKey.CANONICAL_LOCATOR,
        sidecar_prefix="local/personal-memory/",
        fixture_ids_required=False,
    ),
    "task3-guardrails": StudyFixtureSpec(
        name="task3-guardrails",
        task=3,
        file_stem="task-3-guardrails",
        expected_count=75,
        syntax=FixtureSyntax.TASK3_INLINE,
        context_name="local/guardrails",
        purpose_sidecar_stem="task-3-memory-purpose",
        purpose_sidecar_count=476,
        purpose_sidecar_key=PurposeSidecarKey.CANONICAL_LOCATOR,
        sidecar_prefix="local/guardrails/",
        fixture_ids_required=False,
    ),
    "task3-healthcare-qna": StudyFixtureSpec(
        name="task3-healthcare-qna",
        task=3,
        file_stem="task-3-healthcare-information-request",
        expected_count=75,
        syntax=FixtureSyntax.TASK3_INLINE,
        context_name=(
            "remote/government/healthcare-agent/info-request/questions-and-answers"
        ),
        purpose_sidecar_stem="task-3-memory-purpose",
        purpose_sidecar_count=476,
        purpose_sidecar_key=PurposeSidecarKey.CANONICAL_LOCATOR,
        sidecar_prefix=(
            "remote/government/healthcare-agent/info-request/questions-and-answers/"
        ),
        fixture_ids_required=False,
        query_only=True,
    ),
    "task3-healthcare-public-guidance": StudyFixtureSpec(
        name="task3-healthcare-public-guidance",
        task=3,
        file_stem="task-3-healthcare-public-guidance",
        expected_count=25,
        syntax=FixtureSyntax.TASK3_INLINE,
        context_name=(
            "remote/government/healthcare-agent/info-request/transmission-guidance"
        ),
        purpose_sidecar_stem="task-3-memory-purpose",
        purpose_sidecar_count=476,
        purpose_sidecar_key=PurposeSidecarKey.CANONICAL_LOCATOR,
        sidecar_prefix=(
            "remote/government/healthcare-agent/info-request/transmission-guidance/"
        ),
        fixture_ids_required=False,
    ),
}


_TASK1_HEADING = re.compile(r"^###\s+(T1-[UWQ]-\d{3})\s*$")
_TASK2_RECORD = re.compile(
    # Description fixtures reuse the compact inline form even for Task 1.
    # Keeping the authored task prefix in the ID prevents cross-task identity
    # collisions while leaving the established Task 2 L/R/Q grammar intact.
    r"^-\s+(?P<id>T(?:1-D|2-[DLRQ])-\d{3})\s+—\s+"
    r"`(?P<locator>[^`]+)`\s+—\s+"
    r"(?P<purpose>[A-Z]{2})\s+—\s+(?P<content>\S.*)$"
)
_TASK3_RECORD = re.compile(
    r"^-\s+(?P<locator>\S+)\s+"
    r"\[(?P<purpose>[A-Z]{2})\]\s+(?P<content>\S.*)$"
)
_FIELD_LINE = re.compile(r"^-\s+([^:]+):\s*(.*)$")
_LANGUAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")

_LOCATION_LABELS = frozenset(
    {"Memory 위치", "Memory Location", "Memory location"}
)
_CONTENT_LABELS = frozenset({"본문", "Content"})
_AUDIENCE_LABELS = frozenset({"열람 대상", "Audience"})
_VERIFIED_LABELS = frozenset({"Verified", "verified", "검수", "검증"})
_PURPOSE_LABELS = frozenset({"목적", "Purpose", "purpose"})

_AUDIENCE_PHRASES = (
    ("Construction/Facilities Personnel", "__OPERATIONS__"),
    ("Construction and Facilities Personnel", "__OPERATIONS__"),
    ("공사·건물 관계자", "__OPERATIONS__"),
    ("Faculty/Staff", "__STAFF__"),
)
_AUDIENCE_TOKENS = {
    "전체": AudienceRole.ALL,
    "All": AudienceRole.ALL,
    "방문자": AudienceRole.VISITOR,
    "Visitor": AudienceRole.VISITOR,
    "Visitors": AudienceRole.VISITOR,
    "학생": AudienceRole.STUDENT,
    "Student": AudienceRole.STUDENT,
    "Students": AudienceRole.STUDENT,
    "교직원": AudienceRole.STAFF,
    "Staff": AudienceRole.STAFF,
    "__STAFF__": AudienceRole.STAFF,
    "__OPERATIONS__": AudienceRole.CONSTRUCTION_FACILITIES,
}


@dataclass(frozen=True)
class _RawRecord:
    fixture_id: str | None
    locator: str
    content: str
    purpose: str | None
    audiences: tuple[AudienceRole, ...]
    verified: bool | None
    source_line: int


@dataclass(frozen=True)
class _PurposeEntry:
    fixture_id: str | None
    canonical_locator: str | None
    purpose: str
    audiences: tuple[AudienceRole, ...] | None
    verified: bool | None


def default_fixture_root() -> Path:
    """Return the repository's language-partitioned fixture directory."""

    return Path(__file__).resolve().parents[2] / "docs" / "fixtures"


def load_study_fixture(
    dataset: str | StudyFixtureSpec,
    *,
    language: str = "ko",
    root: Path | None = None,
) -> FixtureDataset:
    """Load and validate one Markdown dataset and its purpose sidecar."""

    spec = _resolve_spec(dataset)
    language = _validate_language(language)
    fixture_root = Path(root) if root is not None else default_fixture_root()
    source_path = _resolve_language_file(
        fixture_root, language, spec.file_stem, ".md"
    )
    sidecar_path = _resolve_language_file(
        fixture_root,
        language,
        spec.purpose_sidecar_stem,
        ".tsv",
    )

    raw_records = _parse_markdown(source_path, spec.syntax)
    sidecar = _load_purpose_sidecar(sidecar_path, spec)
    records = _merge_and_validate(
        raw_records,
        sidecar,
        spec=spec,
        language=language,
        source_path=source_path,
    )
    return FixtureDataset(spec=spec, language=language, records=records)


def load_study_fixture_corpus(
    *,
    language: str = "ko",
    root: Path | None = None,
) -> FixtureCorpus:
    """Load all Task 1--3 datasets and validate corpus-wide identities."""

    datasets = tuple(
        load_study_fixture(spec, language=language, root=root)
        for spec in STUDY_FIXTURE_SPECS.values()
    )
    corpus = FixtureCorpus(language=_validate_language(language), datasets=datasets)
    records = corpus.records
    if len(records) != EXPECTED_CORPUS_COUNT:
        raise StudyFixtureError(
            f"Expected {EXPECTED_CORPUS_COUNT} corpus records, found "
            f"{len(records)}."
        )
    _reject_duplicates(
        (record.canonical_locator for record in records),
        "canonical Memory locator across corpus",
    )
    fixture_ids = [
        record.fixture_id for record in records if record.fixture_id is not None
    ]
    _reject_duplicates(fixture_ids, "fixture ID across corpus")
    return corpus


def pair_fixture_translations(
    canonical: FixtureDataset,
    translation: FixtureDataset,
) -> tuple[FixtureTranslationPair, ...]:
    """Pair two languages without allowing metadata or identity drift.

    A later builder should allocate one UID for each pair's ``uid_key`` and
    reuse that UID when writing ``canonical.content`` and
    ``translation.content`` to their respective Contexts.  This loader does
    not mutate a Memory store or silently claim that translations are equal.
    """

    if canonical.spec.name != translation.spec.name:
        raise StudyFixtureError(
            "Cannot pair different datasets: "
            f"{canonical.spec.name!r} and {translation.spec.name!r}."
        )
    if canonical.language == translation.language:
        raise StudyFixtureError(
            "Canonical and translation datasets must use different languages."
        )

    translated_by_locator = translation.by_locator()
    canonical_locators = {
        record.canonical_locator for record in canonical.records
    }
    translated_locators = set(translated_by_locator)
    if canonical_locators != translated_locators:
        missing = sorted(canonical_locators - translated_locators)
        extra = sorted(translated_locators - canonical_locators)
        raise StudyFixtureError(
            "Translation locator set differs from canonical dataset; "
            f"missing={missing[:5]}, extra={extra[:5]}."
        )

    pairs: list[FixtureTranslationPair] = []
    for source in canonical.records:
        target = translated_by_locator[source.canonical_locator]
        if source.fixture_id != target.fixture_id:
            raise StudyFixtureError(
                f"Fixture ID drift at {source.canonical_locator!r}: "
                f"{source.fixture_id!r} != {target.fixture_id!r}."
            )
        if source.purpose != target.purpose:
            raise StudyFixtureError(
                f"Purpose drift at {source.canonical_locator!r}: "
                f"{source.purpose!r} != {target.purpose!r}."
            )
        if source.audiences != target.audiences:
            raise StudyFixtureError(
                f"Audience drift at {source.canonical_locator!r}."
            )
        if source.verified != target.verified:
            raise StudyFixtureError(
                f"Verified-state drift at {source.canonical_locator!r}."
            )
        pairs.append(
            FixtureTranslationPair(canonical=source, translation=target)
        )
    return tuple(pairs)


def _resolve_spec(dataset: str | StudyFixtureSpec) -> StudyFixtureSpec:
    if isinstance(dataset, StudyFixtureSpec):
        return dataset
    try:
        return STUDY_FIXTURE_SPECS[dataset]
    except KeyError as error:
        raise StudyFixtureError(
            f"Unknown study fixture dataset {dataset!r}."
        ) from error


def _validate_language(language: str) -> str:
    value = language.strip()
    if not _LANGUAGE.fullmatch(value):
        raise StudyFixtureError(f"Invalid fixture language {language!r}.")
    return value


def _resolve_language_file(
    root: Path,
    language: str,
    stem: str,
    suffix: str,
) -> Path:
    language_root = root / language
    candidates = (
        language_root / f"{stem}-{language}{suffix}",
        language_root / f"{stem}{suffix}",
    )
    existing = [path for path in candidates if path.is_file()]
    if len(existing) == 1:
        return existing[0]
    if len(existing) > 1:
        raise StudyFixtureError(
            f"Ambiguous fixture files for {stem!r} in {language_root}: "
            + ", ".join(path.name for path in existing)
        )
    raise StudyFixtureError(
        f"Missing fixture file for {stem!r}; expected "
        + " or ".join(str(path) for path in candidates)
        + "."
    )


def _parse_markdown(
    path: Path,
    syntax: FixtureSyntax,
) -> tuple[_RawRecord, ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if syntax is FixtureSyntax.TASK1_BLOCK:
        return _parse_task1_blocks(lines, path)
    if syntax is FixtureSyntax.TASK2_INLINE:
        return _parse_task2_inline(lines, path)
    if syntax is FixtureSyntax.TASK3_INLINE:
        return _parse_task3_inline(lines, path)
    raise StudyFixtureError(f"Unsupported fixture syntax {syntax!r}.")


def _parse_task1_blocks(
    lines: list[str],
    path: Path,
) -> tuple[_RawRecord, ...]:
    starts = [
        (index, match.group(1))
        for index, line in enumerate(lines)
        if (match := _TASK1_HEADING.fullmatch(line)) is not None
    ]
    records: list[_RawRecord] = []
    for position, (start, fixture_id) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        fields = _parse_block_fields(lines[start + 1 : end], start + 2, path)
        locator = _required_field(fields, _LOCATION_LABELS, fixture_id, path)
        content = _required_field(fields, _CONTENT_LABELS, fixture_id, path)
        audience_text = _required_field(
            fields, _AUDIENCE_LABELS, fixture_id, path
        )
        purpose_text = _optional_field(fields, _PURPOSE_LABELS)
        purpose = _validate_purpose(purpose_text, path) if purpose_text else None
        verified_text = _optional_field(fields, _VERIFIED_LABELS)
        verified = (
            _parse_verified(verified_text, path) if verified_text else None
        )
        records.append(
            _RawRecord(
                fixture_id=fixture_id,
                locator=locator,
                content=content,
                purpose=purpose,
                audiences=_parse_audiences(audience_text, path),
                verified=verified,
                source_line=start + 1,
            )
        )
    return tuple(records)


def _parse_block_fields(
    lines: list[str],
    first_line_number: int,
    path: Path,
) -> dict[str, str]:
    fields: dict[str, str] = {}
    active_label: str | None = None
    for offset, line in enumerate(lines):
        match = _FIELD_LINE.fullmatch(line)
        if match is not None:
            label = match.group(1).strip()
            if label in fields:
                raise StudyFixtureError(
                    f"Duplicate field {label!r} at "
                    f"{path}:{first_line_number + offset}."
                )
            fields[label] = match.group(2).strip()
            active_label = label
            continue
        if active_label is not None and line.startswith(("  ", "\t")):
            continuation = line.strip()
            if continuation:
                fields[active_label] = (
                    f"{fields[active_label]} {continuation}"
                ).strip()
            continue
        active_label = None
    return fields


def _parse_task2_inline(
    lines: list[str],
    path: Path,
) -> tuple[_RawRecord, ...]:
    records: list[_RawRecord] = []
    for line_number, line in enumerate(lines, start=1):
        match = _TASK2_RECORD.fullmatch(line)
        if match is None:
            continue
        records.append(
            _RawRecord(
                fixture_id=match.group("id"),
                locator=match.group("locator").strip(),
                content=match.group("content").strip(),
                purpose=_validate_purpose(match.group("purpose"), path),
                audiences=(),
                verified=None,
                source_line=line_number,
            )
        )
    return tuple(records)


def _parse_task3_inline(
    lines: list[str],
    path: Path,
) -> tuple[_RawRecord, ...]:
    records: list[_RawRecord] = []
    for line_number, line in enumerate(lines, start=1):
        match = _TASK3_RECORD.fullmatch(line)
        if match is None:
            continue
        records.append(
            _RawRecord(
                fixture_id=None,
                locator=match.group("locator").strip(),
                content=match.group("content").strip(),
                purpose=_validate_purpose(match.group("purpose"), path),
                audiences=(),
                verified=None,
                source_line=line_number,
            )
        )
    return tuple(records)


def _required_field(
    fields: Mapping[str, str],
    labels: frozenset[str],
    fixture_id: str,
    path: Path,
) -> str:
    value = _optional_field(fields, labels)
    if not value:
        raise StudyFixtureError(
            f"Record {fixture_id!r} in {path} is missing "
            f"one of {sorted(labels)!r}."
        )
    return value


def _optional_field(
    fields: Mapping[str, str],
    labels: frozenset[str],
) -> str | None:
    matches = [fields[label] for label in labels if label in fields]
    if len(matches) > 1:
        raise StudyFixtureError(
            f"Record uses more than one equivalent field label: "
            f"{sorted(label for label in labels if label in fields)!r}."
        )
    return matches[0] if matches else None


def _parse_audiences(value: str, path: Path) -> tuple[AudienceRole, ...]:
    normalized = value.strip()
    for phrase, replacement in _AUDIENCE_PHRASES:
        normalized = normalized.replace(phrase, replacement)
    pieces = [piece.strip() for piece in re.split(r"\s*[·,;]\s*", normalized)]
    audiences: list[AudienceRole] = []
    for piece in pieces:
        if not piece:
            continue
        try:
            role = _AUDIENCE_TOKENS[piece]
        except KeyError as error:
            raise StudyFixtureError(
                f"Unknown audience label {piece!r} in {path}."
            ) from error
        if role in audiences:
            raise StudyFixtureError(
                f"Duplicate audience label {piece!r} in {path}."
            )
        audiences.append(role)
    if not audiences:
        raise StudyFixtureError(f"Empty audience metadata in {path}.")
    if AudienceRole.ALL in audiences and len(audiences) != 1:
        raise StudyFixtureError(
            f"Audience 'all' cannot be combined with other roles in {path}."
        )
    return tuple(audiences)


def _parse_verified(value: str, path: Path) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"true", "yes", "y", "1", "checked", "✓", "예"}:
        return True
    if normalized in {"false", "no", "n", "0", "unchecked", "아니오"}:
        return False
    raise StudyFixtureError(f"Invalid Verified value {value!r} in {path}.")


def _validate_purpose(value: str, path: Path) -> str:
    purpose = value.strip()
    purpose = _PURPOSE_NAMES.get(purpose, purpose)
    if purpose not in PURPOSE_CODES:
        raise StudyFixtureError(
            f"Unknown purpose code {purpose!r} in {path}; "
            f"expected one of {sorted(PURPOSE_CODES)!r}."
        )
    return purpose


def _canonical_locator(context_name: str, locator: str, path: Path) -> str:
    value = locator.strip()
    if not value or value.startswith(("/", "\\")) or "\\" in value:
        raise StudyFixtureError(f"Unsafe Memory locator {locator!r} in {path}.")
    pieces = value.split("/")
    if any(piece in {"", ".", ".."} for piece in pieces):
        raise StudyFixtureError(f"Unsafe Memory locator {locator!r} in {path}.")
    if value == context_name or value.startswith(f"{context_name}/"):
        return value
    return f"{context_name}/{value}"


def _load_purpose_sidecar(
    path: Path,
    spec: StudyFixtureSpec,
) -> dict[str, _PurposeEntry]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t", strict=True)
        if reader.fieldnames is None:
            raise StudyFixtureError(f"Missing TSV header in {path}.")
        id_column = _find_column(reader.fieldnames, {"fixture_id", "Fixture ID"})
        locator_column = _find_column(
            reader.fieldnames,
            {"Memory 위치", "memory_location", "Memory Location"},
        )
        purpose_column = _find_column(
            reader.fieldnames,
            {"목적 코드", "목적", "Purpose", "purpose", "purpose_code"},
        )
        if purpose_column is None:
            purpose_column = _find_column(
                reader.fieldnames,
                {"메모리 목적", "Memory Purpose", "memory_purpose"},
                required=True,
            )
        audience_column = _find_column(
            reader.fieldnames,
            {"열람 대상", "Audience", "audience"},
        )
        verified_column = _find_column(
            reader.fieldnames,
            {"Verified", "verified", "검수", "검증"},
        )
        if spec.purpose_sidecar_key is PurposeSidecarKey.FIXTURE_ID:
            if id_column is None:
                raise StudyFixtureError(
                    f"Purpose sidecar {path} requires a fixture_id column."
                )
            key_column = id_column
        else:
            if locator_column is None:
                raise StudyFixtureError(
                    f"Purpose sidecar {path} requires a Memory locator column."
                )
            key_column = locator_column

        all_entries: dict[str, _PurposeEntry] = {}
        row_count = 0
        for line_number, row in enumerate(reader, start=2):
            row_count += 1
            key = (row.get(key_column) or "").strip()
            if not key:
                raise StudyFixtureError(f"Empty sidecar key at {path}:{line_number}.")
            if key in all_entries:
                raise StudyFixtureError(
                    f"Duplicate sidecar key {key!r} at {path}:{line_number}."
                )
            fixture_id = (row.get(id_column) or "").strip() if id_column else None
            locator = (
                (row.get(locator_column) or "").strip()
                if locator_column
                else None
            )
            purpose = _validate_purpose(row.get(purpose_column) or "", path)
            audience_value = (
                (row.get(audience_column) or "").strip()
                if audience_column
                else ""
            )
            verified_value = (
                (row.get(verified_column) or "").strip()
                if verified_column
                else ""
            )
            all_entries[key] = _PurposeEntry(
                fixture_id=fixture_id or None,
                canonical_locator=locator or None,
                purpose=purpose,
                audiences=(
                    _parse_audiences(audience_value, path)
                    if audience_value
                    else None
                ),
                verified=(
                    _parse_verified(verified_value, path)
                    if verified_value
                    else None
                ),
            )
    if row_count != spec.purpose_sidecar_count:
        raise StudyFixtureError(
            f"Purpose sidecar {path} expected {spec.purpose_sidecar_count} "
            f"rows, found {row_count}."
        )
    subset = {
        key: entry
        for key, entry in all_entries.items()
        if key.startswith(spec.sidecar_prefix)
    }
    if len(subset) != spec.expected_count:
        raise StudyFixtureError(
            f"Purpose sidecar subset {spec.sidecar_prefix!r} expected "
            f"{spec.expected_count} rows, found {len(subset)}."
        )
    return subset


def _find_column(
    headers: Iterable[str],
    aliases: set[str],
    *,
    required: bool = False,
) -> str | None:
    matches = [header for header in headers if header in aliases]
    if len(matches) > 1:
        raise StudyFixtureError(
            f"TSV has multiple equivalent columns {matches!r}."
        )
    if not matches:
        if required:
            raise StudyFixtureError(
                f"TSV is missing one of the required columns {sorted(aliases)!r}."
            )
        return None
    return matches[0]


def _merge_and_validate(
    raw_records: tuple[_RawRecord, ...],
    sidecar: Mapping[str, _PurposeEntry],
    *,
    spec: StudyFixtureSpec,
    language: str,
    source_path: Path,
) -> tuple[FixtureMemory, ...]:
    if len(raw_records) != spec.expected_count:
        raise StudyFixtureError(
            f"Fixture {source_path} expected {spec.expected_count} records, "
            f"found {len(raw_records)}."
        )
    fixture_ids = [
        record.fixture_id
        for record in raw_records
        if record.fixture_id is not None
    ]
    if spec.fixture_ids_required and len(fixture_ids) != len(raw_records):
        raise StudyFixtureError(f"Fixture IDs are required in {source_path}.")
    if not spec.fixture_ids_required and fixture_ids:
        raise StudyFixtureError(
            f"Fixture IDs are not part of the contract for {source_path}."
        )
    _reject_duplicates(fixture_ids, f"fixture ID in {source_path}")

    records: list[FixtureMemory] = []
    canonical_locators: list[str] = []
    consumed_sidecar_keys: set[str] = set()
    for raw in raw_records:
        locator = raw.locator.strip()
        canonical = _canonical_locator(spec.context_name, locator, source_path)
        canonical_locators.append(canonical)
        if spec.purpose_sidecar_key is PurposeSidecarKey.FIXTURE_ID:
            assert raw.fixture_id is not None
            sidecar_key = raw.fixture_id
        else:
            sidecar_key = canonical
        try:
            metadata = sidecar[sidecar_key]
        except KeyError as error:
            raise StudyFixtureError(
                f"No purpose sidecar row for {sidecar_key!r} in {source_path}."
            ) from error
        consumed_sidecar_keys.add(sidecar_key)
        if metadata.fixture_id and metadata.fixture_id != raw.fixture_id:
            raise StudyFixtureError(
                f"Fixture ID mismatch for {sidecar_key!r} in {source_path}."
            )
        if metadata.canonical_locator:
            sidecar_locator = _canonical_locator(
                spec.context_name,
                metadata.canonical_locator,
                source_path,
            )
            if sidecar_locator != canonical:
                raise StudyFixtureError(
                    f"Memory locator mismatch for {sidecar_key!r}: "
                    f"{canonical!r} != {sidecar_locator!r}."
                )
        if raw.purpose is not None and raw.purpose != metadata.purpose:
            raise StudyFixtureError(
                f"Purpose mismatch for {sidecar_key!r}: "
                f"{raw.purpose!r} != {metadata.purpose!r}."
            )
        if (
            metadata.audiences is not None
            and raw.audiences
            and metadata.audiences != raw.audiences
        ):
            raise StudyFixtureError(
                f"Audience mismatch for {sidecar_key!r} in {source_path}."
            )
        if (
            metadata.verified is not None
            and raw.verified is not None
            and metadata.verified != raw.verified
        ):
            raise StudyFixtureError(
                f"Verified-state mismatch for {sidecar_key!r} in {source_path}."
            )
        content = raw.content.strip()
        if not content:
            raise StudyFixtureError(
                f"Empty Memory content for {sidecar_key!r} in {source_path}."
            )
        records.append(
            FixtureMemory(
                dataset=spec.name,
                language=language,
                fixture_id=raw.fixture_id,
                locator=locator,
                canonical_locator=canonical,
                content=content,
                purpose=metadata.purpose,
                audiences=metadata.audiences or raw.audiences,
                verified=(
                    metadata.verified
                    if metadata.verified is not None
                    else raw.verified
                ),
                source_path=source_path,
                source_line=raw.source_line,
            )
        )
    _reject_duplicates(
        canonical_locators, f"canonical Memory locator in {source_path}"
    )
    unused = set(sidecar) - consumed_sidecar_keys
    if unused:
        raise StudyFixtureError(
            f"Purpose sidecar has {len(unused)} unconsumed rows for "
            f"{spec.name}: {sorted(unused)[:5]!r}."
        )
    return tuple(records)


def _reject_duplicates(values: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise StudyFixtureError(
            f"Duplicate {label}: {sorted(duplicates)[:5]!r}."
        )

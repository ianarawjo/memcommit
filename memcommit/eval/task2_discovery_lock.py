"""Frozen calibration identity for Task 2 relation discovery.

The discovery corpus is intentionally consumed while the provider pipeline is
optimized, so this lock must never be described as an independent holdout.  It
freezes both the reviewed 150-vs-150 corpus and the four progressive slices
used to reach that full scale.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path

from memcommit.eval.task2_discovery import (
    TASK2_RELATION_BANDS,
    Task2DiscoveryCorpus,
    Task2DiscoveryInput,
    build_task2_discovery_input,
    load_task2_discovery_corpus,
)


DEFAULT_TASK2_DISCOVERY_LOCK = (
    Path(__file__).parent / "fixtures" / "task2_discovery.lock.json"
)
LEGACY_TASK2_DISCOVERY_LOCK = (
    Path(__file__).parent / "fixtures" / "task2_discovery.v1.lock.json"
)
TASK2_DISCOVERY_LOCK_KIND = "memcommit.semantic-eval.task2-discovery-lock"
TASK2_DISCOVERY_LOCK_SCHEMA_VERSION = 2
TASK2_DISCOVERY_LEGACY_SCHEMA_VERSION = 1
TASK2_DISCOVERY_LOCK_REVISION = "task2-relation-discovery-calibration-v2"
TASK2_DISCOVERY_LOCK_SLICES = (26, 50, 100, 138)
TASK2_DISCOVERY_EVALUATION_CONDITION = "CONTENT_PLUS_TOPIC"
TASK2_DISCOVERY_SELECTION = "FIRST_REVIEWED_GROUPS_CALIBRATION"


class Task2DiscoveryLockError(RuntimeError):
    """The lock is malformed or no longer matches the discovery corpus."""


@dataclass(frozen=True)
class Task2DiscoverySliceLock:
    group_count: int
    selected_left_count: int
    selected_right_count: int
    input_digest: str
    alias_mapping_digest: str
    gold_relations_digest: str
    band_distribution: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Task2DiscoveryLock:
    path: Path
    schema_version: int
    revision: str
    language: str
    corpus_digest: str
    sidecar_fixture: str
    sidecar_digest: str
    full_left_count: int
    full_right_count: int
    full_group_count: int
    slices: tuple[Task2DiscoverySliceLock, ...]
    frozen_at: str
    independent_holdout: bool
    consumed_during_optimization: bool


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _positive_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise Task2DiscoveryLockError(
            f"Task 2 discovery lock {field} must be a positive integer."
        )
    return value


def _sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise Task2DiscoveryLockError(
            f"Task 2 discovery lock {field} must be a lowercase SHA-256 digest."
        )
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _gold_relations_digest(value: Task2DiscoveryInput) -> str:
    material = [asdict(relation) for relation in value.expected]
    return hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()


def _parse_slice(raw: object, *, index: int) -> Task2DiscoverySliceLock:
    required = {
        "group_count",
        "selected_left_count",
        "selected_right_count",
        "input_digest",
        "alias_mapping_digest",
        "gold_relations_digest",
        "band_distribution",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise Task2DiscoveryLockError(
            f"Task 2 discovery lock slice {index} has an invalid contract."
        )
    distribution = raw["band_distribution"]
    if not isinstance(distribution, dict) or set(distribution) != set(
        TASK2_RELATION_BANDS
    ):
        raise Task2DiscoveryLockError(
            f"Task 2 discovery lock slice {index} band distribution is invalid."
        )
    normalized_distribution = tuple(
        (band, _positive_integer(distribution[band], f"slice {index} band {band}"))
        for band in sorted(TASK2_RELATION_BANDS)
    )
    group_count = _positive_integer(raw["group_count"], f"slice {index} group_count")
    if sum(count for _band, count in normalized_distribution) != group_count:
        raise Task2DiscoveryLockError(
            f"Task 2 discovery lock slice {index} band counts do not sum to its groups."
        )
    return Task2DiscoverySliceLock(
        group_count=group_count,
        selected_left_count=_positive_integer(
            raw["selected_left_count"], f"slice {index} selected_left_count"
        ),
        selected_right_count=_positive_integer(
            raw["selected_right_count"], f"slice {index} selected_right_count"
        ),
        input_digest=_sha256(raw["input_digest"], f"slice {index} input_digest"),
        alias_mapping_digest=_sha256(
            raw["alias_mapping_digest"], f"slice {index} alias_mapping_digest"
        ),
        gold_relations_digest=_sha256(
            raw["gold_relations_digest"], f"slice {index} gold_relations_digest"
        ),
        band_distribution=normalized_distribution,
    )


def load_task2_discovery_lock(path: Path | None = None) -> Task2DiscoveryLock:
    """Load the strict lock without opening the corpus or relation sidecar."""
    lock_path = path or DEFAULT_TASK2_DISCOVERY_LOCK
    try:
        value = json.loads(
            lock_path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise Task2DiscoveryLockError(
            "The Task 2 discovery lock is not valid strict UTF-8 JSON."
        ) from error
    common_required = {
        "kind",
        "schema_version",
        "operation",
        "corpus_role",
        "language",
        "selection",
        "evaluation_condition",
        "semantic_evidence_fields",
        "corpus_digest",
        "sidecar_fixture",
        "sidecar_sha256",
        "full_left_count",
        "full_right_count",
        "full_group_count",
        "slices",
        "frozen_at",
        "independent_holdout",
        "consumed_during_optimization",
    }
    if not isinstance(value, dict):
        raise Task2DiscoveryLockError(
            "The Task 2 discovery lock has an invalid top-level contract."
        )
    schema_version = value.get("schema_version")
    if schema_version == TASK2_DISCOVERY_LEGACY_SCHEMA_VERSION:
        required = common_required
        revision = "task2-relation-discovery-calibration-v1"
    elif schema_version == TASK2_DISCOVERY_LOCK_SCHEMA_VERSION:
        required = common_required | {"revision"}
        revision = value.get("revision")
        if revision != TASK2_DISCOVERY_LOCK_REVISION:
            raise Task2DiscoveryLockError(
                "The Task 2 discovery lock revision is invalid."
            )
    else:
        raise Task2DiscoveryLockError(
            "The Task 2 discovery lock schema version is unsupported."
        )
    if set(value) != required:
        raise Task2DiscoveryLockError(
            "The Task 2 discovery lock has an invalid top-level contract."
        )
    if (
        value["kind"] != TASK2_DISCOVERY_LOCK_KIND
        or value["operation"] != "task2-relation-discovery"
        or value["corpus_role"] != "CALIBRATION"
        or value["language"] != "en"
        or value["selection"] != TASK2_DISCOVERY_SELECTION
        or value["evaluation_condition"] != TASK2_DISCOVERY_EVALUATION_CONDITION
        or value["semantic_evidence_fields"] != ["content", "topic"]
        or value["independent_holdout"] is not False
        or value["consumed_during_optimization"] is not True
    ):
        raise Task2DiscoveryLockError(
            "The Task 2 discovery lock identity or calibration boundary is invalid."
        )
    frozen_at = value["frozen_at"]
    if not isinstance(frozen_at, str):
        raise Task2DiscoveryLockError("Task 2 discovery lock frozen_at is invalid.")
    try:
        datetime.strptime(frozen_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise Task2DiscoveryLockError(
            "Task 2 discovery lock frozen_at must be UTC second precision."
        ) from error
    raw_slices = value["slices"]
    if not isinstance(raw_slices, list):
        raise Task2DiscoveryLockError("Task 2 discovery lock slices are invalid.")
    slices = tuple(
        _parse_slice(raw, index=index)
        for index, raw in enumerate(raw_slices, start=1)
    )
    if tuple(item.group_count for item in slices) != TASK2_DISCOVERY_LOCK_SLICES:
        raise Task2DiscoveryLockError(
            "Task 2 discovery lock must contain the 26, 50, 100, and 138 group slices."
        )
    sidecar_fixture = value["sidecar_fixture"]
    if sidecar_fixture != "task-2-pair-relations-en.tsv":
        raise Task2DiscoveryLockError(
            "Task 2 discovery lock sidecar fixture is invalid."
        )
    full_left_count = _positive_integer(value["full_left_count"], "full_left_count")
    full_right_count = _positive_integer(value["full_right_count"], "full_right_count")
    full_group_count = _positive_integer(value["full_group_count"], "full_group_count")
    if (full_left_count, full_right_count, full_group_count) != (150, 150, 138):
        raise Task2DiscoveryLockError(
            "Task 2 discovery lock full-corpus counts are invalid."
        )
    return Task2DiscoveryLock(
        path=lock_path,
        schema_version=schema_version,
        revision=revision,
        language="en",
        corpus_digest=_sha256(value["corpus_digest"], "corpus_digest"),
        sidecar_fixture=sidecar_fixture,
        sidecar_digest=_sha256(value["sidecar_sha256"], "sidecar_sha256"),
        full_left_count=full_left_count,
        full_right_count=full_right_count,
        full_group_count=full_group_count,
        slices=slices,
        frozen_at=frozen_at,
        independent_holdout=False,
        consumed_during_optimization=True,
    )


def validate_task2_discovery_lock(
    lock: Task2DiscoveryLock,
    *,
    root: Path | None = None,
) -> Task2DiscoveryCorpus:
    """Rebuild every locked slice and fail closed on any corpus drift."""
    corpus = load_task2_discovery_corpus(language=lock.language, root=root)
    try:
        sidecar_digest = hashlib.sha256(corpus.sidecar_path.read_bytes()).hexdigest()
    except OSError as error:
        raise Task2DiscoveryLockError(
            "The locked Task 2 relation sidecar cannot be read."
        ) from error
    if (
        corpus.digest != lock.corpus_digest
        or corpus.sidecar_path.name != lock.sidecar_fixture
        or sidecar_digest != lock.sidecar_digest
        or len(corpus.left) != lock.full_left_count
        or len(corpus.right) != lock.full_right_count
        or len(corpus.relations) != lock.full_group_count
    ):
        raise Task2DiscoveryLockError(
            "The Task 2 discovery corpus no longer matches the frozen calibration lock."
        )
    for manifest in lock.slices:
        value = build_task2_discovery_input(corpus, group_count=manifest.group_count)
        distribution = tuple(
            sorted(Counter(relation.band for relation in value.expected).items())
        )
        if (
            len(value.left_items) != manifest.selected_left_count
            or len(value.right_items) != manifest.selected_right_count
            or value.input_digest != manifest.input_digest
            or value.alias_mapping_digest != manifest.alias_mapping_digest
            or _gold_relations_digest(value) != manifest.gold_relations_digest
            or distribution != manifest.band_distribution
        ):
            raise Task2DiscoveryLockError(
                f"Task 2 discovery slice {manifest.group_count} no longer matches "
                "the frozen calibration lock."
            )
    return corpus


def load_and_validate_task2_discovery_lock(
    path: Path | None = None,
    *,
    root: Path | None = None,
) -> tuple[Task2DiscoveryLock, Task2DiscoveryCorpus]:
    """Load the lock and replay all four progressive slice manifests."""
    lock = load_task2_discovery_lock(path)
    return lock, validate_task2_discovery_lock(lock, root=root)
